"""
Chat routes - Message sending, history, clear
NOW USES USERNAME-BASED HISTORY (syncs across all devices)
INCLUDES: 25 messages/day hard limit for regular users, unlimited for Creator
FIXED: History scoped by session_id to prevent cross-mode context bleed
ADDED: Image analysis via base64 image in chat request
MIGRATED: From Gemini to Groq - fully free, no Google dependency
ADDED: /conversations/{username} endpoint for chat history sidebar
FIXED: Smart search detection for Serbian + English
FIXED: Context-aware search (uses previous message when user says "search for it")
FIXED: When search fails, model says "I don't know" instead of hallucinating
FIXED: Long-term memory now actually saved after conversations (was never being written)
ADDED: URL fetching — Sanctumly can now open and read links users share
ADDED: /chat/stream — Server-Sent Events streaming for token-by-token responses
"""

import logging
import os
import re
import json
import base64
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
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
)
from app.services import retrieve_relevant_context, search_web, fetch_url, extract_urls
from app.services.memory import get_conversation_memory, update_conversation_memory
from app.services.therapist_kb import get_therapist_knowledge_context
from app.prompts import get_system_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])

# Configure Groq client
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)

# Model selection
GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_VISION_MODEL = "llama-3.2-90b-vision-preview"

# Daily message limit for regular users
DAILY_MESSAGE_LIMIT = 25

# Max image size: 4MB base64 (roughly 3MB actual image)
MAX_IMAGE_SIZE = 4 * 1024 * 1024


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

def get_daily_message_count(db: Session, username: str) -> int:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.query(func.count(Message.id)).filter(
        Message.username == username.lower(),
        Message.role == "user",
        Message.timestamp >= today_start
    ).scalar()
    return count or 0


def check_daily_limit(db: Session, username: str, is_creator: bool):
    if is_creator:
        return
    count = get_daily_message_count(db, username)
    if count >= DAILY_MESSAGE_LIMIT:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today_start + timedelta(days=1)
        hours_until_reset = (tomorrow - datetime.utcnow()).total_seconds() / 3600
        raise HTTPException(
            status_code=429,
            detail={
                "error": "daily_limit_exceeded",
                "message": f"Daily message limit ({DAILY_MESSAGE_LIMIT}) reached. Resets in {hours_until_reset:.1f} hours.",
                "limit": DAILY_MESSAGE_LIMIT,
                "used": count,
                "reset_time": tomorrow.isoformat() + "Z"
            }
        )


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


def save_memory(username: str, history_messages, last_response: str, db: Session):
    """Extract and save long-term memory from recent conversation using Groq."""
    try:
        recent = "\n".join([
            f"{'User' if m.role == 'user' else 'Sanctumly'}: {m.content}"
            for m in reversed(history_messages[-10:])
        ])
        recent += f"\nSanctumly: {last_response}"

        extract_prompt = f"""Based on this conversation, extract concise information about the user.

Conversation:
{recent}

Respond in this EXACT format with no extra text:
SUMMARY: (2-3 sentences about what this person is dealing with)
KEY_FACTS: (age, situation, relationships, struggles — comma separated)
PREFERENCES: (how they like to be spoken to, what helps them — comma separated)"""

        mem_response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": extract_prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        text = mem_response.choices[0].message.content

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


def build_chat_context(request: ChatRequest, db: Session, is_creator: bool):
    """
    Shared context builder used by BOTH /message and /stream.
    Returns (messages, history_messages, meta) where meta carries flags for logging.
    Does NOT handle images (caller handles those separately for /message).
    """
    username = request.username
    session_id = sanitize_session_id(request.session_id)

    # ---- URL fetching ----
    url_context = ""
    urls = extract_urls(request.message)
    if urls:
        for url in urls[:2]:
            content = fetch_url(url)
            if content:
                url_context += content + "\n"
        if url_context:
            logger.info(f"🌐 URL fetch: loaded content from {len(urls)} URL(s)")

    # ---- RAG ----
    rag_context = retrieve_relevant_context(request.message, session_id, db)

    # ---- Memory (therapist only) ----
    memory_context = ""
    if request.personality == "therapist":
        memory = get_conversation_memory(username, db)
        if memory:
            memory_context = f"\nWhat you remember about {username}:\n{memory['summary']}\nKey things: {memory['key_facts']}\nTheir preferences: {memory['preferences']}\n"

    # ---- System prompt ----
    system_prompt = get_system_prompt(is_creator, username, request.personality)

    if url_context:
        system_prompt += f"\n\nContent fetched from URL(s) the user shared:\n{url_context}"
    if rag_context:
        system_prompt += f"\n\nRelevant context from uploaded documents:\n{rag_context}"
    if memory_context:
        system_prompt += f"\n\n{memory_context}"
    if request.personality == "therapist":
        therapist_context = get_therapist_knowledge_context(db)
        if therapist_context:
            system_prompt += f"\n\nProfessional therapeutic guidance (use naturally, don't quote directly):\n{therapist_context}"

    # ---- History ----
    history_messages = db.query(Message).filter_by(session_id=session_id)\
        .order_by(Message.timestamp.desc()).limit(12).all()

    messages = [{"role": "system", "content": system_prompt}]
    for msg in reversed(history_messages):
        messages.append({
            "role": "user" if msg.role == "user" else "assistant",
            "content": msg.content
        })

    # ---- Web search (skip if URL content already fetched) ----
    might_need_search = should_search(request.message) and not url_context
    if might_need_search:
        if is_reference_search(request.message):
            previous_topic = get_search_context_from_history(history_messages)
            search_query = extract_search_query(previous_topic) if previous_topic else extract_search_query(request.message)
        else:
            search_query = extract_search_query(request.message)

        logger.info(f"🔍 Search | Query: '{search_query}'")
        search_result = search_web(search_query)
        if search_result:
            system_prompt += f"\n\nWeb search results for reference:\n{search_result}\n\nUse ONLY these search results to answer factual questions. Do not add information beyond what the search results contain. If the results don't fully answer the question, say what you found and note what you're unsure about."
            logger.info("✅ Web search: Added results to context")
        else:
            system_prompt += "\n\nIMPORTANT: The user asked a factual question. Web search was attempted but returned NO results. You MUST NOT guess or make up an answer. Tell the user you tried to search but couldn't find results right now, and suggest they look it up themselves. Do NOT invent dates, facts, or details."
            logger.info("⚠️ Search failed — injected anti-hallucination instruction")
        messages[0]["content"] = system_prompt

    meta = {
        "urls": urls or [],
        "had_url_context": bool(url_context),
        "had_rag_context": bool(rag_context),
        "had_memory": bool(memory_context),
        "searched": might_need_search,
    }
    return messages, history_messages, meta


# ============================================================
# ROUTES
# ============================================================

@router.get("/rate-limit/status/{username}")
async def get_rate_limit_status(username: str, db: Session = Depends(get_db)):
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
    account = db.query(Account).filter_by(username=username.lower()).first()
    if not account:
        raise HTTPException(status_code=404, detail="User not found")
    if account.is_creator:
        return {
            "username": username, "is_creator": True, "unlimited": True,
            "message_count": 0, "messages_remaining": "unlimited",
            "daily_limit": DAILY_MESSAGE_LIMIT, "reset_time": None
        }
    count = get_daily_message_count(db, username)
    messages_remaining = max(0, DAILY_MESSAGE_LIMIT - count)
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today_start + timedelta(days=1)
    return {
        "username": username, "is_creator": False, "unlimited": False,
        "message_count": count, "messages_remaining": messages_remaining,
        "daily_limit": DAILY_MESSAGE_LIMIT, "reset_time": tomorrow.isoformat() + "Z"
    }


@router.get("/conversations/{username}")
async def get_conversations(username: str, limit: int = 30, db: Session = Depends(get_db)):
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
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
async def get_session_history(session_id: str, limit: int = 100, db: Session = Depends(get_db)):
    session_id = sanitize_session_id(session_id)
    messages = db.query(Message).filter_by(session_id=session_id)\
        .order_by(Message.timestamp.desc()).limit(limit).all()
    return {
        "messages": [
            {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp.isoformat()}
            for msg in reversed(messages)
        ]
    }


@router.post("/message")
async def chat_message(request: ChatRequest, db: Session = Depends(get_db)):
    """Send message - history scoped by SESSION to prevent cross-mode bleed"""
    username = request.username
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username format")

    session_id = sanitize_session_id(request.session_id)

    if not verify_session_ownership_flexible(session_id, username, db):
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid session")

    account = db.query(Account).filter_by(username=username.lower()).first()
    is_creator = account.is_creator if account else False

    check_daily_limit(db, username, is_creator)

    if not check_message_rate_limit(username, db):
        raise HTTPException(status_code=429, detail="Message rate limit exceeded. Maximum 30 messages per hour.")

    log_message_request(username, db)

    # Validate image if provided
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
            logger.info(f"🖼️ Image attached: {image_mime}, {len(clean_b64)} chars base64")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image data")

    logger.info(f"💬 Chat - User: {username}, Creator: {is_creator}, Mode: {request.personality}, Image: {has_image}")

    # Build shared context (URL fetch, RAG, memory, search, history)
    messages, history_messages, meta = build_chat_context(request, db, is_creator)

    # Build current user message (with image if present)
    if has_image:
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_b64}"}},
            {"type": "text", "text": request.message}
        ]
        messages.append({"role": "user", "content": user_content})
        model_to_use = GROQ_VISION_MODEL
    else:
        messages.append({"role": "user", "content": request.message})
        model_to_use = GROQ_MODEL

    try:
        response = groq_client.chat.completions.create(
            model=model_to_use, messages=messages,
            temperature=0.7, top_p=0.95, max_tokens=4096,
        )
        response_text = response.choices[0].message.content

        saved_content = f"[Image attached] {request.message}" if has_image else request.message

        user_msg = Message(session_id=session_id, username=username.lower(), role="user", content=saved_content)
        assistant_msg = Message(session_id=session_id, username=username.lower(), role="assistant", content=response_text)
        db.add(user_msg)
        db.add(assistant_msg)
        db.commit()

        # ---- SAVE LONG-TERM MEMORY every 6 user messages (therapist mode only) ----
        if request.personality == "therapist":
            user_msg_count = get_daily_message_count(db, username)
            if user_msg_count % 6 == 0:
                save_memory(username, history_messages, response_text, db)

        remaining = "unlimited" if is_creator else max(0, DAILY_MESSAGE_LIMIT - get_daily_message_count(db, username))
        logger.info(f"✅ Response: {len(response_text)} chars | Remaining: {remaining} | Image: {has_image} | Model: {model_to_use} | Searched: {meta['searched']} | URLs: {len(meta['urls'])}")

        return {
            "response": response_text, "session_id": session_id,
            "had_rag_context": meta["had_rag_context"], "had_memory": meta["had_memory"],
            "had_url_context": meta["had_url_context"],
            "messages_remaining": remaining
        }

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_message_stream(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Streaming version of /chat/message — returns Server-Sent Events (SSE).
    Each event is a JSON line:
      {"type": "token", "content": "..."}            incremental text
      {"type": "done", "messages_remaining": N}      final, after full text saved
      {"type": "error", "message": "..."}            on failure
    Images are NOT supported here (vision is non-streaming) — client falls back to /message.
    """
    username = request.username
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username format")

    session_id = sanitize_session_id(request.session_id)

    if not verify_session_ownership_flexible(session_id, username, db):
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid session")

    account = db.query(Account).filter_by(username=username.lower()).first()
    is_creator = account.is_creator if account else False

    check_daily_limit(db, username, is_creator)

    if not check_message_rate_limit(username, db):
        raise HTTPException(status_code=429, detail="Message rate limit exceeded. Maximum 30 messages per hour.")

    log_message_request(username, db)

    if request.image:
        raise HTTPException(status_code=400, detail="Image messages must use /chat/message, not /chat/stream")

    logger.info(f"💬 Stream - User: {username}, Creator: {is_creator}, Mode: {request.personality}")

    # Build shared context (URL fetch, RAG, memory, search, history)
    messages, history_messages, meta = build_chat_context(request, db, is_creator)
    messages.append({"role": "user", "content": request.message})

    def event_generator():
        full_text = ""
        try:
            stream = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.7,
                top_p=0.95,
                max_tokens=4096,
                stream=True,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta
                token = getattr(delta, "content", None)
                if token:
                    full_text += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            # Stream finished — persist both messages
            user_msg = Message(session_id=session_id, username=username.lower(), role="user", content=request.message)
            assistant_msg = Message(session_id=session_id, username=username.lower(), role="assistant", content=full_text)
            db.add(user_msg)
            db.add(assistant_msg)
            db.commit()

            # Long-term memory (therapist mode), same cadence as /message
            if request.personality == "therapist":
                user_msg_count = get_daily_message_count(db, username)
                if user_msg_count % 6 == 0:
                    save_memory(username, history_messages, full_text, db)

            remaining = "unlimited" if is_creator else max(0, DAILY_MESSAGE_LIMIT - get_daily_message_count(db, username))
            logger.info(f"✅ Stream done: {len(full_text)} chars | Remaining: {remaining} | Searched: {meta['searched']} | URLs: {len(meta['urls'])}")

            yield f"data: {json.dumps({'type': 'done', 'messages_remaining': remaining, 'session_id': session_id})}\n\n"

        except Exception as e:
            logger.error(f"❌ Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

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
async def get_chat_history(username: str, limit: int = 50, db: Session = Depends(get_db)):
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
    messages = db.query(Message).filter_by(username=username.lower())\
        .order_by(Message.timestamp.desc()).limit(limit).all()
    return {
        "messages": [
            {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp.isoformat()}
            for msg in reversed(messages)
        ]
    }


@router.delete("/clear/{session_id}")
async def clear_chat(session_id: str, db: Session = Depends(get_db)):
    session_id = sanitize_session_id(session_id)
    deleted = db.query(Message).filter_by(session_id=session_id).delete()
    db.commit()
    logger.info(f"🗑️ Cleared {deleted} messages for session: {session_id[:30]}...")
    return {"success": True, "message": f"Chat cleared ({deleted} messages)"}
