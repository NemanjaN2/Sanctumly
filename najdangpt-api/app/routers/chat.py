"""
Chat routes - Message sending, history, clear
NOW USES USERNAME-BASED HISTORY (syncs across all devices)
INCLUDES: 20 messages/day hard limit for regular users, unlimited for Creator
FIXED: History scoped by session_id to prevent cross-mode context bleed
ADDED: Image analysis via base64 image in chat request
MIGRATED: From Gemini to Groq (Llama 3.3 70B) - fully free, no Google dependency
"""

import logging
import os
import base64
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
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
from app.services import retrieve_relevant_context, search_web
from app.services.memory import get_conversation_memory
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
GROQ_MODEL = "moonshotai/kimi-k2-instruct-0905"
GROQ_VISION_MODEL = "llama-3.2-90b-vision-preview"

# Daily message limit for regular users
DAILY_MESSAGE_LIMIT = 25

# Max image size: 4MB base64 (roughly 3MB actual image)
MAX_IMAGE_SIZE = 4 * 1024 * 1024


def get_daily_message_count(db: Session, username: str) -> int:
    """Get user's message count for today (UTC)"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    count = db.query(func.count(Message.id)).filter(
        Message.username == username.lower(),
        Message.role == "user",
        Message.timestamp >= today_start
    ).scalar()
    
    return count or 0


def check_daily_limit(db: Session, username: str, is_creator: bool):
    """
    Check if user has exceeded daily message limit.
    Creator is exempt. Raises HTTPException if limit exceeded.
    """
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
    """Detect image MIME type from base64 data"""
    if base64_data.startswith("data:"):
        mime = base64_data.split(";")[0].split(":")[1]
        return mime
    
    try:
        raw = base64.b64decode(base64_data[:32])
        if raw[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        elif raw[:2] == b'\xff\xd8':
            return "image/jpeg"
        elif raw[:4] == b'GIF8':
            return "image/gif"
        elif raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
            return "image/webp"
    except Exception:
        pass
    
    return "image/jpeg"


def clean_base64(base64_data: str) -> str:
    """Strip data URI prefix if present"""
    if "," in base64_data and base64_data.startswith("data:"):
        return base64_data.split(",", 1)[1]
    return base64_data


@router.get("/rate-limit/status/{username}")
async def get_rate_limit_status(username: str, db: Session = Depends(get_db)):
    """Get rate limit status for a user"""
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
    
    account = db.query(Account).filter_by(username=username.lower()).first()
    if not account:
        raise HTTPException(status_code=404, detail="User not found")
    
    if account.is_creator:
        return {
            "username": username,
            "is_creator": True,
            "unlimited": True,
            "message_count": 0,
            "messages_remaining": "unlimited",
            "daily_limit": DAILY_MESSAGE_LIMIT,
            "reset_time": None
        }
    
    count = get_daily_message_count(db, username)
    messages_remaining = max(0, DAILY_MESSAGE_LIMIT - count)
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today_start + timedelta(days=1)
    
    return {
        "username": username,
        "is_creator": False,
        "unlimited": False,
        "message_count": count,
        "messages_remaining": messages_remaining,
        "daily_limit": DAILY_MESSAGE_LIMIT,
        "reset_time": tomorrow.isoformat() + "Z"
    }


@router.post("/message")
async def chat_message(request: ChatRequest, db: Session = Depends(get_db)):
    """Send message - history scoped by SESSION to prevent cross-mode bleed"""
    username = request.username
    
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username format")
    
    session_id = sanitize_session_id(request.session_id)
    
    # Verify session ownership
    if not verify_session_ownership_flexible(session_id, username, db):
        raise HTTPException(
            status_code=403,
            detail="Unauthorized: Invalid session"
        )
    
    account = db.query(Account).filter_by(username=username.lower()).first()
    is_creator = account.is_creator if account else False
    
    # Check DAILY limit first (hard limit: 20/day for regular users)
    check_daily_limit(db, username, is_creator)
    
    # Then check hourly rate limit (spam protection: 30/hour)
    if not check_message_rate_limit(username, db):
        raise HTTPException(
            status_code=429,
            detail="Message rate limit exceeded. Maximum 30 messages per hour."
        )
    
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
    
    # Get RAG context from uploaded documents (session-scoped)
    rag_context = retrieve_relevant_context(request.message, session_id, db)
    
    # Get conversation memory - ONLY for wellness mode
    memory_context = ""
    if request.personality == "therapist":
        memory = get_conversation_memory(username, db)
        if memory:
            memory_context = f"""
What you remember about {username}:
{memory['summary']}
Key things: {memory['key_facts']}
Their preferences: {memory['preferences']}
"""
    
    # Get system prompt
    system_prompt = get_system_prompt(is_creator, username, request.personality)
    
    # Add RAG context
    if rag_context:
        system_prompt += f"\n\nRelevant context from uploaded documents:\n{rag_context}"
        logger.info(f"✅ RAG: Retrieved context from documents")
    
    # Add memory context (wellness only)
    if memory_context:
        system_prompt += f"\n\n{memory_context}"
        logger.info(f"✅ Memory: Loaded user memory (wellness mode)")
    
    # Add therapist knowledge base (wellness only)
    if request.personality == "therapist":
        therapist_context = get_therapist_knowledge_context(db)
        if therapist_context:
            system_prompt += f"\n\nProfessional therapeutic guidance (use naturally, don't quote directly):\n{therapist_context}"
            logger.info(f"✅ Therapist KB: Loaded professional knowledge")
    
    # FIXED: Get conversation history BY SESSION_ID (not username)
    history_messages = db.query(Message)\
        .filter_by(session_id=session_id)\
        .order_by(Message.timestamp.desc())\
        .limit(20)\
        .all()
    
    # Build OpenAI-compatible message format for Groq
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    for msg in reversed(history_messages):
        messages.append({
            "role": "user" if msg.role == "user" else "assistant",
            "content": msg.content
        })
    
    # Check if web search might be needed
    search_keywords = ['latest', 'current', 'recent', 'today', 'now', 'news', 'price', 'stock', 'weather', 
                       'what is', 'who is', 'when did', 'how much', 'what are']
    might_need_search = any(keyword in request.message.lower() for keyword in search_keywords)
    
    if might_need_search:
        logger.info(f"🔍 Search triggered for: {request.message}")
        search_result = search_web(request.message)
        if search_result:
            system_prompt += f"\n\nLive web search results:\n{search_result}\n\nUse this information to answer. Don't say you can't access real-time data."
            # Update system message with search results
            messages[0]["content"] = system_prompt
            logger.info(f"✅ Web search: Added results to context")
    
    # Build the current user message
    if has_image:
        # Use vision model for image analysis
        user_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_mime};base64,{image_b64}"
                }
            },
            {
                "type": "text",
                "text": request.message
            }
        ]
        messages.append({"role": "user", "content": user_content})
        model_to_use = GROQ_VISION_MODEL
    else:
        messages.append({"role": "user", "content": request.message})
        model_to_use = GROQ_MODEL
    
    try:
        response = groq_client.chat.completions.create(
            model=model_to_use,
            messages=messages,
            temperature=0.7,
            top_p=0.95,
            max_tokens=8192,
        )
        
        response_text = response.choices[0].message.content
        
        # Save messages (store text only, not the image)
        saved_content = request.message
        if has_image:
            saved_content = f"[Image attached] {request.message}"
        
        user_msg = Message(
            session_id=session_id,
            username=username.lower(),
            role="user",
            content=saved_content
        )
        assistant_msg = Message(
            session_id=session_id,
            username=username.lower(),
            role="assistant",
            content=response_text
        )
        db.add(user_msg)
        db.add(assistant_msg)
        db.commit()
        
        # Get remaining messages for response
        remaining = "unlimited" if is_creator else max(0, DAILY_MESSAGE_LIMIT - get_daily_message_count(db, username))
        
        logger.info(f"✅ Response: {len(response_text)} chars | Remaining: {remaining} | Image: {has_image} | Model: {model_to_use}")
        
        return {
            "response": response_text,
            "session_id": session_id,
            "had_rag_context": bool(rag_context),
            "had_memory": bool(memory_context),
            "messages_remaining": remaining
        }
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{username}")
async def get_chat_history(username: str, limit: int = 50, db: Session = Depends(get_db)):
    """Get chat history for a USER (syncs across all devices)"""
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
    
    messages = db.query(Message)\
        .filter_by(username=username.lower())\
        .order_by(Message.timestamp.desc())\
        .limit(limit)\
        .all()
    
    return {
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in reversed(messages)
        ]
    }


@router.delete("/clear/{session_id}")
async def clear_chat(session_id: str, db: Session = Depends(get_db)):
    """Clear chat history for current session only"""
    session_id = sanitize_session_id(session_id)
    
    deleted = db.query(Message).filter_by(session_id=session_id).delete()
    db.commit()
    
    logger.info(f"🗑️ Cleared {deleted} messages for session: {session_id[:30]}...")
    return {"success": True, "message": f"Chat cleared ({deleted} messages)"}
