"""Chat routes, conversation history, and adaptive text-model routing.

Text requests use Cloudflare Gemma when configured and fall back to Groq
GPT-OSS-120B for quota exhaustion, provider errors, and high-complexity work.
Vision, transcription, and speech generation retain their existing providers.
"""

import logging
import os
import re
import json
import base64
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from openai import OpenAI

from app.database import get_db
from app.schemas.chat import ChatRequest
from app.models.account import Account
from app.models.chat import Message
from app.security import (
    validate_username,
    sanitize_session_id,
    verify_session_ownership_flexible,
    check_message_rate_limit,
    log_message_request,
    require_user,
)
from app.security.dependencies import authenticate_session_token, extract_bearer_token, require_creator
from app.security.conversations import authorize_conversation_session
from app.services import retrieve_relevant_context, search_web, fetch_url, extract_urls
from app.services.memory import get_conversation_memory, update_conversation_memory
from app.services.therapist_kb import get_therapist_knowledge_context
from app.prompts import get_system_prompt, PERSONALITIES
from app.config import (
    FREE_DAILY_TEXT_REQUESTS, FREE_MAX_OUTPUT_TOKENS, MAX_MESSAGE_CHARS,
    SERPER_API_KEY, SERPER_USD_PER_SEARCH,
    CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_MODEL,
    HISTORY_TOKEN_BUDGET, CREATOR_HISTORY_TOKEN_BUDGET,
    RETRIEVED_CONTEXT_TOKEN_BUDGET, CREATOR_RETRIEVED_CONTEXT_TOKEN_BUDGET,
)
from app.ai.router import generate_text
from app.ai.context_budget import fit_context_sections, select_recent_history
from app.ai.provider_state import cloudflare_provider_snapshot
from app.security.usage import (
    is_creator_account, consume_quota, reserve_ai_budget, settle_ai_budget,
    add_fixed_cost, estimate_chat_cost, calculate_chat_cost, estimate_input_tokens, usage_snapshot,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])

# Configure Groq client
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY, timeout=30.0, max_retries=1
)

# Model selection
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")

# Daily message limit for regular users
DAILY_MESSAGE_LIMIT = FREE_DAILY_TEXT_REQUESTS

# Max image size: 4MB base64 (roughly 3MB actual image)
MAX_IMAGE_SIZE = 4 * 1024 * 1024


def _resolve_chat_identity(username: str, session_id: str, authorization: str | None, db: Session) -> tuple[Account, str]:
    """Authenticate the caller separately from the per-conversation context ID.

    Modern web clients send their server login token as Bearer auth and a
    separate local conversation ID in the request body. Native legacy clients
    send the server-issued login token in both places. Both contracts work.
    """
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username format")

    raw_id = (session_id or "").strip()
    clean_id = sanitize_session_id(raw_id)
    if not clean_id or clean_id != raw_id or len(clean_id) > 100:
        raise HTTPException(status_code=400, detail="A valid session_id is required")

    if authorization:
        account = authenticate_session_token(extract_bearer_token(authorization), db)
        if account.username.lower() != username.lower():
            raise HTTPException(status_code=403, detail="Authenticated account does not match username")
    else:
        # Backward compatibility for older mobile clients which used the
        # server-issued bearer token as their conversation identifier.
        if not verify_session_ownership_flexible(clean_id, username, db):
            raise HTTPException(status_code=403, detail="Unauthorized: Invalid session")
        account = db.query(Account).filter_by(username=username.lower()).first()
        if not account:
            raise HTTPException(status_code=401, detail="Account not found")

    authorize_conversation_session(clean_id, account, db)
    return account, clean_id


# ============================================================
# SMART SEARCH DETECTION (Serbian + English)
# ============================================================

def should_search(message: str) -> bool:
    msg_lower = message.lower().strip()

    explicit_triggers = [
        "pretraži", "pretražii", "pretrazi", "pogledaj", "nađi", "nadji",
        "potraži", "potrazi", "proveri", "guglaj", "google",
        "pretraži internet", "pretrazi internet", "pogledaj na netu",
        "nađi mi", "nadji mi", "proveri na internetu",
        "search", "look up", "google", "find out", "look it up",
        "search the web", "search online", "search internet",
        "can you search", "can you find", "can you look up",
    ]
    for trigger in explicit_triggers:
        if trigger in msg_lower:
            return True

    serbian_patterns = [
        r'\bkada\s+(je|su|će|ce)\b',
        r'\bkad\s+(je|izlazi|izašao|izasao|izašla|izasla)\b',
        r'\bko\s+(je|su)\b',
        r'\bšta\s+(je|su|znači|znaci)\b',
        r'\bsta\s+(je|su|znaci)\b',
        r'\bgde\s+(je|su)\b',
        r'\bkoliko\s+(je|košta|kosta|ima)\b',
        r'\bkoja\s+(je|su)\b',
        r'\bkoji\s+(je|su)\b',
        r'\bda\s+li\s+(je|su|ima|postoji)\b',
        r'\bodakle\b',
        r'\bkako\s+se\s+(zove|kaže|kaze)\b',
    ]
    for pattern in serbian_patterns:
        if re.search(pattern, msg_lower):
            return True

    english_patterns = [
        r'\bwho\s+(is|are|was|were)\b',
        r'\bwhat\s+(is|are|was|were|does|did|happened)\b',
        r'\bwhen\s+(is|are|was|were|did|does|will)\b',
        r'\bwhere\s+(is|are|was|were|did|does|can)\b',
        r'\bhow\s+(much|many|old|long|far|do|does|did|is)\b',
    ]
    for pattern in english_patterns:
        if re.search(pattern, msg_lower):
            return True

    topic_triggers = [
        'latest', 'current', 'recent', 'today', 'now', 'news',
        'price', 'stock', 'weather', 'forecast', 'temperature',
        'score', 'release date', 'released', 'trending',
        'najnovije', 'najnoviji', 'trenutno', 'danas', 'vesti', 'vest',
        'cena', 'cene', 'vreme', 'prognoza', 'temperatura',
        'rezultat', 'izašao', 'izasao', 'izašla', 'izasla',
        'izlazi', 'premijera', 'pesma', 'pesme', 'film',
        'utakmica', 'meč', 'mec', 'pevačica', 'pevacica',
        'pevač', 'pevac', 'album', 'singl',
    ]
    for trigger in topic_triggers:
        if trigger in msg_lower:
            return True

    if re.search(r'\b(202[3-9]|203\d)\b', msg_lower):
        return True

    if '?' in message:
        words = message.split()
        if len(words) > 2:
            proper_nouns = [w for w in words[1:] if w and w[0].isupper() and len(w) > 1]
            if proper_nouns:
                return True

    return False


def is_reference_search(message: str) -> bool:
    msg_lower = message.lower().strip()
    reference_patterns = [
        r'^(pretraži|pretrazi|pogledaj|proveri|nadji|nађi)\s*(internet|net|online)?\s*(pa|i)?\s*(vidi|pogledaj|proveri)?[.!?]?\s*$',
        r'^(look it up|search for it|google it|find it|check it|search it)[.!?]?\s*$',
        r'^(pretraži|pretrazi|pogledaj)\s*(to|ovo)?[.!?]?\s*$',
    ]
    for pattern in reference_patterns:
        if re.search(pattern, msg_lower):
            return True
    return False


def get_search_context_from_history(history_messages) -> str:
    for msg in history_messages:
        if msg.role == "user":
            content = msg.content
            if content.startswith('[Image attached]'):
                content = content.replace('[Image attached] ', '')
            if content.strip() and len(content.strip()) > 2:
                return content.strip()
    return ""


def extract_search_query(message: str) -> str:
    q = message.strip()
    fillers = [
        r'^(hej|ej|ćao|cao|zdravo|brate|buraz),?\s*',
        r'\b(možeš li|mozes li|molim te|da li možeš|da li mozes)\b\s*',
        r'\b(pretraži|pretrazi|pogledaj|nађi|nadji|potraži|potrazi|proveri)\s*(mi\s*)?(na internetu\s*|na netu\s*|online\s*)?',
        r'\b(reci mi|kaži mi|kazi mi)\s*',
        r'\b(da li znaš|da li znas|znaš li|znas li)\s*',
        r'\b(i vidi|i pogledaj|i proveri|pa vidi|pa pogledaj|pa proveri)\s*',
        r'^(hey|hi|hello|yo),?\s*',
        r'\b(can you|could you|please|would you)\b\s*',
        r'\b(search for|look up|find|search|google)\b\s*',
        r'\b(tell me about|tell me|show me)\b\s*',
        r'\b(do you know|i want to know)\b\s*',
    ]
    for pattern in fillers:
        q = re.sub(pattern, '', q, flags=re.IGNORECASE)
    q = re.sub(r'\s+', ' ', q).strip().rstrip('?!.')
    if len(q) < 3:
        q = message.strip().rstrip('?!.')
    return q[:120]


# ============================================================
# HELPERS
# ============================================================

def get_total_user_message_count(db: Session, username: str) -> int:
    """Count lifetime user messages for the existing every-sixth-message memory cadence."""
    count = db.query(func.count(Message.id)).filter(
        Message.username == username.lower(),
        Message.role == "user",
    ).scalar()
    return count or 0


def detect_image_mime(base64_data: str) -> str:
    if base64_data.startswith("data:"):
        return base64_data.split(";")[0].split(":")[1]
    try:
        raw = base64.b64decode(base64_data[:32])
        if raw[:8] == b'\x89PNG\r\n\x1a\n': return "image/png"
        elif raw[:2] == b'\xff\xd8': return "image/jpeg"
        elif raw[:4] == b'GIF8': return "image/gif"
        elif raw[:4] == b'RIFF' and raw[8:12] == b'WEBP': return "image/webp"
    except Exception: pass
    return "image/jpeg"


def clean_base64(base64_data: str) -> str:
    if "," in base64_data and base64_data.startswith("data:"):
        return base64_data.split(",", 1)[1]
    return base64_data


def save_memory(username: str, history_messages, last_response: str, db: Session, account: Account):
    """Extract and save long-term memory, including its provider cost in the free-tier budget."""
    try:
        recent = "\n".join([
            f"{'User' if m.role == 'user' else 'Sanctumly'}: {m.content}"
            for m in reversed(history_messages[-10:])
        ])
        recent += f"\nSanctumly: {last_response}"
        if not is_creator_account(account):
            recent = recent[-MEMORY_WINDOW_CHARS:]

        extract_prompt = f"""Based on this conversation, extract concise information about the user.

Conversation:
{recent}

Respond in this EXACT format with no extra text:
SUMMARY: (2-3 sentences about what this person is dealing with)
KEY_FACTS: (age, situation, relationships, struggles — comma separated)
PREFERENCES: (how they like to be spoken to, what helps them — comma separated)"""

        memory_messages = [{"role": "user", "content": extract_prompt}]
        reservation = None
        try:
            reservation = reserve_ai_budget(
                account, db, estimate_chat_cost(memory_messages, 300, vision=False)
            )
        except HTTPException as limit_error:
            if limit_error.status_code == 429:
                logger.info("Skipping automatic memory extraction: daily AI budget reached for %s", username)
                return
            raise
        try:
            mem_response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=memory_messages,
                temperature=0.3,
                max_tokens=300,
                extra_body={"reasoning_effort": "low"},
            )
            text = mem_response.choices[0].message.content or ""
            actual_cost = calculate_chat_cost(
                getattr(mem_response, "usage", None),
                fallback_input_tokens=estimate_input_tokens(memory_messages),
                fallback_output_tokens=max(1, len(text) // 3),
            )
            settle_ai_budget(db, reservation, actual_cost)
            reservation = None
        except Exception:
            if reservation is not None:
                settle_ai_budget(db, reservation, 0.0)
            raise

        summary_match = re.search(r'SUMMARY:\s*(.+?)(?=KEY_FACTS:|$)', text, re.DOTALL)
        key_facts_match = re.search(r'KEY_FACTS:\s*(.+?)(?=PREFERENCES:|$)', text, re.DOTALL)
        preferences_match = re.search(r'PREFERENCES:\s*(.+?)$', text, re.DOTALL)

        summary = summary_match.group(1).strip() if summary_match else ""
        key_facts = key_facts_match.group(1).strip() if key_facts_match else ""
        preferences = preferences_match.group(1).strip() if preferences_match else ""

        if summary:
            update_conversation_memory(username, summary, key_facts, preferences, db)
            logger.info(f"✅ Memory saved for {username}")
        else:
            logger.warning(f"⚠️ Memory extraction returned empty summary for {username}")

    except Exception as e:
        logger.error(f"⚠️ Memory save failed for {username}: {e}")


HISTORY_MESSAGE_LIMIT = int(os.environ.get("HISTORY_MESSAGE_LIMIT", "10"))
HISTORY_MSG_MAX_CHARS = int(os.environ.get("HISTORY_MSG_MAX_CHARS", "1500"))
HISTORY_MSG_MAX_CHARS_CREATOR = int(os.environ.get("HISTORY_MSG_MAX_CHARS_CREATOR", "5000"))
MEMORY_WINDOW_CHARS = int(os.environ.get("MEMORY_WINDOW_CHARS", "6000"))

# Per-section ceilings prevent one retrieved source from crowding out every
# other source. The combined cap is enforced below for each request.
URL_CONTEXT_MAX_TOKENS = int(os.environ.get("URL_CONTEXT_MAX_TOKENS", "1800"))
RAG_CONTEXT_MAX_TOKENS = int(os.environ.get("RAG_CONTEXT_MAX_TOKENS", "1600"))
SEARCH_CONTEXT_MAX_TOKENS = int(os.environ.get("SEARCH_CONTEXT_MAX_TOKENS", "1800"))
MEMORY_CONTEXT_MAX_TOKENS = int(os.environ.get("MEMORY_CONTEXT_MAX_TOKENS", "450"))
THERAPIST_CONTEXT_MAX_TOKENS = int(os.environ.get("THERAPIST_CONTEXT_MAX_TOKENS", "900"))


def _trim_history(text: str, limit: int = HISTORY_MSG_MAX_CHARS) -> str:
    """Legacy-compatible per-message ceiling; total history is capped separately."""
    if not text or len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " [...]"


def build_chat_context(request: ChatRequest, db: Session, account: Account):
    """Build a bounded system/retrieval/history context for /message and /stream.

    The current user message is appended by the route after this function, so
    it is never discarded by history trimming. Creator access remains unlimited
    at the account/quota level; Creator receives a larger per-request context
    budget, not a daily usage cap.
    """
    username = request.username
    session_id = sanitize_session_id(request.session_id)
    is_creator = is_creator_account(account)

    # Query the existing history count limit first. Token budgeting below adds
    # a second bound so a few very long messages cannot dominate each request.
    history_rows = db.query(Message).filter_by(session_id=session_id)\
        .order_by(Message.timestamp.desc()).limit(12 if is_creator else HISTORY_MESSAGE_LIMIT).all()

    # ---- URL fetching ----
    url_context = ""
    urls = extract_urls(request.message)
    if urls:
        for url in urls[:2]:
            content = fetch_url(url, is_creator)
            if content:
                url_context += content + "\n"
        if url_context:
            logger.info("URL fetch: loaded content from %s URL(s)", len(urls[:2]))

    # ---- RAG and memory ----
    rag_context = retrieve_relevant_context(request.message, session_id, db) or ""

    memory_context = ""
    if request.personality == "therapist":
        memory = get_conversation_memory(username, db)
        if memory:
            memory_context = (
                f"What you remember about {username}:\n{memory['summary']}\n"
                f"Key things: {memory['key_facts']}\n"
                f"Their preferences: {memory['preferences']}"
            )

    therapist_context = ""
    if request.personality == "therapist":
        # Even Creator knowledge retrieval is bounded per request. This is not
        # a Creator quota and does not restrict the number of requests.
        therapist_context = get_therapist_knowledge_context(
            db, max_chars=12000 if is_creator else 6000
        ) or ""

    # ---- Web search ----
    might_need_search = should_search(request.message) and not url_context
    search_result = ""
    search_empty = False
    if might_need_search:
        if is_reference_search(request.message):
            previous_topic = get_search_context_from_history(history_rows)
            search_query = (
                extract_search_query(previous_topic)
                if previous_topic else extract_search_query(request.message)
            )
        else:
            search_query = extract_search_query(request.message)

        logger.info("Search | Query: '%s'", search_query)
        if not is_creator:
            consume_quota(account, db, "web_searches", 1)
            if SERPER_API_KEY:
                add_fixed_cost(account, db, SERPER_USD_PER_SEARCH)
        search_result = search_web(search_query, is_creator) or ""
        search_empty = not bool(search_result)
        if search_empty:
            logger.info("Web search returned no results")
        else:
            logger.info("Web search results added to bounded context")

    # Keep the prompt itself byte-identical at the front. Variable URL, search,
    # RAG, memory and therapeutic knowledge are appended after CORE + MODE +
    # CONTEXT and share one explicit retrieval-context token budget.
    base_system_prompt = get_system_prompt(is_creator, username, request.personality)
    context_budget = (
        CREATOR_RETRIEVED_CONTEXT_TOKEN_BUDGET
        if is_creator else RETRIEVED_CONTEXT_TOKEN_BUDGET
    )
    sections = []
    if url_context:
        sections.append(("Content fetched from URL(s) the user shared", url_context, URL_CONTEXT_MAX_TOKENS))
    if search_result:
        sections.append((
            "Web search results (answer factual questions only from these; state what remains unclear)",
            search_result,
            SEARCH_CONTEXT_MAX_TOKENS,
        ))
    elif search_empty:
        sections.append((
            "Web search status",
            "Search returned no results. Say that you tried but found nothing; do not invent facts or dates.",
            100,
        ))
    if rag_context:
        sections.append(("Relevant context from uploaded documents", rag_context, RAG_CONTEXT_MAX_TOKENS))
    if memory_context:
        sections.append(("Conversation memory", memory_context, MEMORY_CONTEXT_MAX_TOKENS))
    if therapist_context:
        sections.append((
            "Professional therapeutic guidance (use naturally; do not quote directly)",
            therapist_context,
            THERAPIST_CONTEXT_MAX_TOKENS,
        ))

    context_suffix, context_tokens, section_usage = fit_context_sections(
        sections, context_budget
    )
    system_prompt = base_system_prompt + context_suffix

    # ---- Token-budgeted history ----
    history_budget = CREATOR_HISTORY_TOKEN_BUDGET if is_creator else HISTORY_TOKEN_BUDGET
    per_message_chars = HISTORY_MSG_MAX_CHARS_CREATOR if is_creator else HISTORY_MSG_MAX_CHARS
    history_messages, provider_history, history_tokens, history_trimmed = select_recent_history(
        history_rows,
        token_budget=history_budget,
        max_chars_per_message=per_message_chars,
    )

    messages = [{"role": "system", "content": system_prompt}, *provider_history]
    total_context_tokens = history_tokens + context_tokens
    logger.info(
        "Context budget | account_type=%s mode=%s history_tokens=%s/%s retrieved_tokens=%s/%s trimmed_messages=%s",
        "creator" if is_creator else "standard",
        request.personality,
        history_tokens,
        history_budget,
        context_tokens,
        context_budget,
        history_trimmed,
    )

    meta = {
        "urls": urls or [],
        "had_url_context": bool(url_context),
        "had_rag_context": bool(rag_context),
        "had_memory": bool(memory_context),
        "searched": might_need_search,
        "history_tokens_estimated": history_tokens,
        "retrieved_context_tokens_estimated": context_tokens,
        "context_sections_tokens": section_usage,
        "history_messages_trimmed": history_trimmed,
        "history_messages_included": len(provider_history),
        "context_tokens_estimated": total_context_tokens,
    }
    return messages, history_messages, meta


# ============================================================
# ROUTES
# ============================================================

@router.get("/provider-status")
async def get_provider_status(account: Account = Depends(require_creator), db: Session = Depends(get_db)):
    """Creator-only diagnostics for the shared provider-level Cloudflare quota."""
    return {
        "cloudflare": cloudflare_provider_snapshot(db),
        "cloudflare_configured": bool(CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN),
        "primary_model": CLOUDFLARE_MODEL,
        "fallback_model": GROQ_MODEL,
        "quota_scope": "shared_by_all_sanctumly_accounts",
    }


@router.get("/modes")
async def list_available_modes(account: Account = Depends(require_user)):
    """Return the modes this authenticated account is allowed to see/use."""
    creator = is_creator_account(account)
    return {"modes": [
        {"id": mode_id, "name": details.get("name", mode_id),
         "description": details.get("description", "")}
        for mode_id, details in PERSONALITIES.items()
        if not details.get("creator_only") or creator
    ]}


def _enforce_personality(personality: str | None, account: Account):
    selected = (personality or "default").strip().lower()
    if selected not in PERSONALITIES:
        raise HTTPException(status_code=400, detail="Unknown assistant mode")
    if PERSONALITIES[selected].get("creator_only") and not is_creator_account(account):
        raise HTTPException(status_code=403, detail="This mode is available only to the creator")
    return selected


@router.get("/rate-limit/status/{username}")
async def get_rate_limit_status(username: str, account: Account = Depends(require_user), db: Session = Depends(get_db)):
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
    if not is_creator_account(account) and account.username.lower() != username.lower():
        raise HTTPException(status_code=403, detail="Forbidden")
    account = db.query(Account).filter_by(username=username.lower()).first()
    if not account:
        raise HTTPException(status_code=404, detail="User not found")
    if is_creator_account(account):
        return {
            "username": username, "is_creator": True, "unlimited": True,
            "message_count": 0, "messages_remaining": "unlimited",
            "daily_limit": DAILY_MESSAGE_LIMIT, "reset_time": None,
            "usage": usage_snapshot(account, db),
        }
    usage = usage_snapshot(account, db)
    count = int(usage.get("text_requests", 0))
    messages_remaining = max(0, DAILY_MESSAGE_LIMIT - count)
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today_start + timedelta(days=1)
    return {
        "username": username, "is_creator": False, "unlimited": False,
        "message_count": count, "messages_remaining": messages_remaining,
        "daily_limit": DAILY_MESSAGE_LIMIT, "reset_time": tomorrow.isoformat() + "Z",
        "usage": usage,
    }


@router.get("/conversations/{username}")
async def get_conversations(username: str, limit: int = 30, account: Account = Depends(require_user), db: Session = Depends(get_db)):
    limit = max(1, min(limit, 100))
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
    if not is_creator_account(account) and account.username.lower() != username.lower():
        raise HTTPException(status_code=403, detail="Forbidden")
    session_stats = db.query(
        Message.session_id,
        func.min(Message.timestamp).label('first_message_at'),
        func.max(Message.timestamp).label('last_message_at'),
        func.count(Message.id).label('message_count')
    ).filter(
        Message.username == username.lower()
    ).group_by(Message.session_id).order_by(
        func.max(Message.timestamp).desc()
    ).limit(limit).all()

    conversations = []
    for stat in session_stats:
        first_msg = db.query(Message.content).filter(
            Message.session_id == stat.session_id, Message.role == 'user'
        ).order_by(Message.timestamp.asc()).first()
        title = first_msg[0][:80] if first_msg else 'New conversation'
        if title.startswith('[Image attached] '): title = title[17:]
        if not title.strip(): title = 'Image analysis'
        conversations.append({
            "session_id": stat.session_id, "title": title,
            "first_message_at": stat.first_message_at.isoformat() if stat.first_message_at else None,
            "last_message_at": stat.last_message_at.isoformat() if stat.last_message_at else None,
            "message_count": stat.message_count
        })
    return {"conversations": conversations}


@router.get("/history/session/{session_id}")
async def get_session_history(session_id: str, limit: int = 100, account: Account = Depends(require_user), db: Session = Depends(get_db)):
    limit = max(1, min(limit, 200))
    session_id = authorize_conversation_session(session_id, account, db)
    messages = db.query(Message).filter_by(session_id=session_id)\
        .order_by(Message.timestamp.desc()).limit(limit).all()
    return {
        "messages": [
            {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp.isoformat()}
            for msg in reversed(messages)
        ]
    }


@router.post("/message")
async def chat_message(request: ChatRequest, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Send a message through the shared adaptive model router."""
    username = request.username
    account, session_id = _resolve_chat_identity(username, request.session_id, authorization, db)
    username = account.username.lower()
    is_creator = is_creator_account(account)
    request.personality = _enforce_personality(request.personality, account)
    if not is_creator and len(request.message or "") > MAX_MESSAGE_CHARS:
        raise HTTPException(status_code=413, detail=f"Message too long. Maximum {MAX_MESSAGE_CHARS} characters on the free plan.")

    if not check_message_rate_limit(username, db):
        raise HTTPException(status_code=429, detail="Message rate limit exceeded. Please try again later.")

    has_image = False
    image_mime = None
    image_b64 = None
    if request.image:
        image_mime = detect_image_mime(request.image)
        clean_b64 = clean_base64(request.image)
        if len(clean_b64) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=400, detail="Image too large. Maximum 4MB.")
        try:
            base64.b64decode(clean_b64)
            image_b64 = clean_b64
            has_image = True
            logger.info("Image attached: %s, %s chars base64", image_mime, len(clean_b64))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image data")

    if not is_creator:
        consume_quota(account, db, "image_analyses" if has_image else "text_requests", 1)
    log_message_request(username, db)
    logger.info("Chat - User: %s, Creator: %s, Mode: %s, Image: %s", username, is_creator, request.personality, has_image)

    messages, history_messages, meta = build_chat_context(request, db, account)
    reservation = None
    try:
        if has_image:
            # Sanctumly keeps image-analysis requests on its existing Groq
            # vision route. The Cloudflare Gemma primary is used for text chat.
            user_content = [
                {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_b64}"}},
                {"type": "text", "text": request.message},
            ]
            messages.append({"role": "user", "content": user_content})
            model_to_use = GROQ_VISION_MODEL
            max_output_tokens = FREE_MAX_OUTPUT_TOKENS if not is_creator else 4096
            reservation = reserve_ai_budget(
                account, db, estimate_chat_cost(messages, max_output_tokens, vision=True)
            )
            completion_kwargs = {
                "model": model_to_use,
                "messages": messages,
                "temperature": 0.7,
                "top_p": 0.95,
            }
            if not is_creator:
                completion_kwargs["max_tokens"] = FREE_MAX_OUTPUT_TOKENS
            response = groq_client.chat.completions.create(**completion_kwargs)
            response_text = response.choices[0].message.content or ""
            if not response_text.strip():
                raise RuntimeError("Groq Vision returned no final answer")
            actual_cost = calculate_chat_cost(
                getattr(response, "usage", None), vision=True,
                fallback_input_tokens=estimate_input_tokens(messages, vision=True),
                fallback_output_tokens=max(1, len(response_text) // 3),
            )
            settle_ai_budget(db, reservation, actual_cost)
            reservation = None
            provider_info = {
                "provider": "groq", "model": model_to_use,
                "routing_reason": "vision_request", "fallback_used": False,
            }
        else:
            messages.append({"role": "user", "content": request.message})
            routed = generate_text(
                messages, account, db, groq_client,
                is_creator=is_creator,
                is_research=bool(meta.get("searched")),
            )
            response_text = routed.content
            model_to_use = routed.model
            provider_info = {
                "provider": routed.provider,
                "model": routed.model,
                "routing_reason": routed.routing_reason,
                "fallback_used": routed.fallback_used,
                "reasoning_effort": routed.reasoning_effort,
            }

        saved_content = f"[Image attached] {request.message}" if has_image else request.message
        user_msg = Message(session_id=session_id, username=username, role="user", content=saved_content)
        assistant_msg = Message(session_id=session_id, username=username, role="assistant", content=response_text)
        db.add(user_msg)
        db.add(assistant_msg)
        db.commit()

        if request.personality == "therapist":
            user_msg_count = get_total_user_message_count(db, username)
            if user_msg_count % 6 == 0:
                save_memory(username, history_messages, response_text, db, account)

        remaining = "unlimited" if is_creator else max(
            0, DAILY_MESSAGE_LIMIT - int(usage_snapshot(account, db).get("text_requests", 0))
        )
        logger.info(
            "Response: %s chars | Remaining: %s | Provider: %s | Model: %s | Route: %s | Fallback: %s | Search: %s",
            len(response_text), remaining, provider_info["provider"], model_to_use,
            provider_info["routing_reason"], provider_info["fallback_used"], meta["searched"],
        )
        return {
            "response": response_text,
            "session_id": session_id,
            "had_rag_context": meta["had_rag_context"],
            "had_memory": meta["had_memory"],
            "had_url_context": meta["had_url_context"],
            "messages_remaining": remaining,
            **provider_info,
        }

    except HTTPException:
        if reservation is not None:
            settle_ai_budget(db, reservation, 0.0)
        raise
    except Exception:
        if reservation is not None:
            settle_ai_budget(db, reservation, 0.0)
        logger.exception("Chat provider error")
        raise HTTPException(status_code=502, detail="AI provider request failed")


@router.post("/stream")
async def chat_message_stream(request: ChatRequest, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """
    SSE-compatible version of /chat/message.
    The upstream model call is buffered/non-streaming, then text is emitted in
    small SSE pieces. This keeps the client event contract while avoiding the
    Cloudflare streaming duplication issue seen during model qualification.
    Each event is a JSON line:
      {"type": "token", "content": "..."}            incremental text
      {"type": "done", "messages_remaining": N}      final, after full text saved
      {"type": "error", "message": "..."}            on failure
    Images are NOT supported here (vision is non-streaming) — client falls back to /message.
    """
    username = request.username
    account, session_id = _resolve_chat_identity(username, request.session_id, authorization, db)
    username = account.username.lower()
    is_creator = is_creator_account(account)
    request.personality = _enforce_personality(request.personality, account)

    if request.image:
        raise HTTPException(status_code=400, detail="Image messages must use /chat/message, not /chat/stream")
    if not is_creator and len(request.message or "") > MAX_MESSAGE_CHARS:
        raise HTTPException(status_code=413, detail=f"Message too long. Maximum {MAX_MESSAGE_CHARS} characters on the free plan.")
    if not check_message_rate_limit(username, db):
        raise HTTPException(status_code=429, detail="Message rate limit exceeded. Please try again later.")
    if not is_creator:
        consume_quota(account, db, "text_requests", 1)
    log_message_request(username, db)

    logger.info(f"💬 Stream - User: {username}, Creator: {is_creator}, Mode: {request.personality}")

    # Build shared context (URL fetch, RAG, memory, search, history)
    messages, history_messages, meta = build_chat_context(request, db, account)
    messages.append({"role": "user", "content": request.message})
    def event_generator():
        full_text = ""
        routed = None
        try:
            # The provider call itself is non-streaming for both models. This
            # preserves the existing SSE client contract while avoiding the
            # upstream streaming duplication issue seen during earlier testing.
            routed = generate_text(
                messages, account, db, groq_client,
                is_creator=is_creator,
                is_research=bool(meta.get("searched")),
            )
            full_text = routed.content
            # Emit the completed response in small pieces to preserve the
            # clients' token-event protocol. Upstream generation is buffered.
            for offset in range(0, len(full_text), 24):
                piece = full_text[offset:offset + 24]
                yield f"data: {json.dumps({'type': 'token', 'content': piece})}\n\n"

            # Provider-specific accounting is settled by generate_text().
            # Stream finished — persist both messages.
            user_msg = Message(session_id=session_id, username=username.lower(), role="user", content=request.message)
            assistant_msg = Message(session_id=session_id, username=username.lower(), role="assistant", content=full_text)
            db.add(user_msg)
            db.add(assistant_msg)
            db.commit()

            # Long-term memory (therapist mode), same cadence as /message
            if request.personality == "therapist":
                user_msg_count = get_total_user_message_count(db, username)
                if user_msg_count % 6 == 0:
                    save_memory(username, history_messages, full_text, db, account)

            remaining = "unlimited" if is_creator else max(0, DAILY_MESSAGE_LIMIT - int(usage_snapshot(account, db).get("text_requests", 0)))
            logger.info(f"✅ Stream done: {len(full_text)} chars | Remaining: {remaining} | Searched: {meta['searched']} | URLs: {len(meta['urls'])}")

            yield f"data: {json.dumps({'type': 'done', 'messages_remaining': remaining, 'session_id': session_id, 'provider': routed.provider, 'model': routed.model, 'routing_reason': routed.routing_reason, 'fallback_used': routed.fallback_used, 'reasoning_effort': routed.reasoning_effort})}\n\n"

        except Exception as e:
            logger.exception("Chat stream error")
            yield f"data: {json.dumps({'type': 'error', 'message': 'AI provider request failed'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering (important on Railway)
        },
    )


@router.get("/history/{username}")
async def get_chat_history(username: str, limit: int = 50, account: Account = Depends(require_user), db: Session = Depends(get_db)):
    limit = max(1, min(limit, 200))
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
    if not is_creator_account(account) and account.username.lower() != username.lower():
        raise HTTPException(status_code=403, detail="Forbidden")
    messages = db.query(Message).filter_by(username=username.lower())\
        .order_by(Message.timestamp.desc()).limit(limit).all()
    return {
        "messages": [
            {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp.isoformat()}
            for msg in reversed(messages)
        ]
    }


@router.delete("/clear/{session_id}")
async def clear_chat(session_id: str, account: Account = Depends(require_user), db: Session = Depends(get_db)):
    session_id = authorize_conversation_session(session_id, account, db)
    deleted = db.query(Message).filter_by(session_id=session_id).delete()
    db.commit()
    logger.info("Cleared %s messages for authenticated conversation", deleted)
    return {"success": True, "message": f"Chat cleared ({deleted} messages)"}
