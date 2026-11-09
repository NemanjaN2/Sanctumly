"""
Sanctumly FastAPI Backend - v9.4.0 Gemma 4 Model Migration
Clean, organized, production-ready
"""

import os
import logging
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends

from app.config import (
    ALLOWED_ORIGINS,
    SUPPORTED_FILE_TYPES,
    MAX_FILE_SIZE,
    FREE_MAX_FILE_SIZE,
    MAX_MESSAGE_CHARS,
    SESSION_EXPIRY_DAYS,
    MAX_ACCOUNTS_PER_HOUR,
    MAX_MESSAGES_PER_HOUR,
    MAX_FAILED_LOGINS_PER_HOUR,
    FREE_DAILY_TEXT_REQUESTS,
    FREE_MAX_OUTPUT_TOKENS,
    FREE_DAILY_IMAGE_ANALYSES,
    FREE_DAILY_WEB_SEARCHES,
    FREE_DAILY_DOCUMENT_UPLOADS,
    FREE_DAILY_TRANSCRIPTION_SECONDS,
    FREE_DAILY_ENGLISH_TTS_CHARS,
    FREE_DAILY_AI_BUDGET_USD,
)
from app.database import init_db, SessionLocal, get_db
from app.models.account import Account, UserSession
from app.security import require_user
from app.models.usage import DailyUsage  # ensure the usage ledger is registered before create_all
from app.models.provider_usage import ProviderDailyUsage  # global Cloudflare Neuron ledger
from app.models.ai_routing_event import AIRoutingEvent  # privacy-minimal routing analytics
from app.models.conversation import ConversationSession  # web/native conversation ownership table
from app.security import (
    hash_password, verify_password, cleanup_old_rate_limit_logs,
    cleanup_expired_sessions, migrate_legacy_session_tokens,
)
from app.routers import auth, chat, upload, memory, feedback, admin, speech, mood, ai_control

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Sanctumly API",
    description="Your AI Companion - Modular Architecture",
    version="9.4.0"
)

# CORS — single source of truth is app/config.ALLOWED_ORIGINS (no wildcard).
# Do NOT redefine the list here; edit config.py so client and server agree.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Register routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(upload.router)
app.include_router(memory.router)
app.include_router(feedback.router)
app.include_router(admin.router)
app.include_router(speech.router)
app.include_router(mood.router)
app.include_router(ai_control.router)


@app.get("/rate-limit/status/{username}", include_in_schema=False)
async def legacy_ios_rate_limit_status(
    username: str,
    account: Account = Depends(require_user),
    db=Depends(get_db),
):
    """Backward-compatible alias used by existing iOS releases.

    Newer Android/web clients call /chat/rate-limit/status/{username}; the
    current iOS client still calls the legacy root-level path. Keep both.
    """
    return await chat.get_rate_limit_status(username, account, db)


def initialize_father_account(db):
    """Ensure Father's account exists with bcrypt password.

    The password is read from the FATHER_PASSWORD environment variable.
    Never hardcode credentials in source. Set FATHER_PASSWORD in Railway.
    """
    father_password = os.environ.get("FATHER_PASSWORD")

    if not father_password:
        logger.warning(
            "⚠️ FATHER_PASSWORD env var not set — skipping Father account init. "
            "Set FATHER_PASSWORD in your environment to manage the creator account."
        )
        return

    father = db.query(Account).filter_by(username='father').first()

    if not father:
        father = Account(
            username='father',
            password_hash=hash_password(father_password),
            is_admin=True,
            is_creator=True
        )
        db.add(father)
        db.commit()
        logger.info("Created Father's account (bcrypt)")
        return

    password_changed = not verify_password(father_password, father.password_hash)
    if password_changed:
        father.password_hash = hash_password(father_password)
        # A configured creator-password rotation invalidates existing sessions.
        db.query(UserSession).filter_by(username='father').delete(synchronize_session=False)
        logger.info("Father password changed from Railway configuration; prior sessions revoked")

    roles_changed = not father.is_admin or not father.is_creator
    father.is_admin = True
    father.is_creator = True
    if password_changed or roles_changed:
        db.commit()
    logger.info("Father account verified")


@app.on_event("startup")
async def startup_event():
    """Initialize database and run startup tasks"""
    init_db()

    db = SessionLocal()
    try:
        migrate_legacy_session_tokens(db)
        initialize_father_account(db)
        cleanup_old_rate_limit_logs(db)
        cleanup_expired_sessions(db)
        logger.info("🚀 Sanctumly API v9.4.0 - Gemma 4 Model Migration")
        logger.info("🔒 Security: bcrypt passwords, session-gated admin, no CORS wildcard")
    finally:
        db.close()


@app.get("/")
async def root():
    """API info endpoint"""
    return {
        "app": "Sanctumly API",
        "version": "9.4.0",
        "architecture": "Modular",
        "ai_engine": "Adaptive Router (Cloudflare Gemma 4 if configured → Groq GPT-OSS 120B)",
        "features": [
            "Secure Sessions (server-generated)",
            "bcrypt Password Hashing",
            "RAG (Document Analysis)",
            "Conversation Memory",
            "Creator Mode",
            "Multi-File Support",
            "Rate Limiting",
            "Web Search",
            "Streaming Responses",
            "Adaptive Gemma/GPT-OSS Model Routing",
            "Shared Provider Quota Tracking",
            "Creator-only AI Control Center"
        ],
        "supported_files": SUPPORTED_FILE_TYPES,
        "rate_limits": {
            "free_daily_text_requests": FREE_DAILY_TEXT_REQUESTS,
            "free_max_output_tokens": FREE_MAX_OUTPUT_TOKENS,
            "free_daily_image_analyses": FREE_DAILY_IMAGE_ANALYSES,
            "free_daily_web_searches": FREE_DAILY_WEB_SEARCHES,
            "free_daily_document_uploads": FREE_DAILY_DOCUMENT_UPLOADS,
            "free_daily_transcription_seconds": FREE_DAILY_TRANSCRIPTION_SECONDS,
            "free_daily_english_tts_characters": FREE_DAILY_ENGLISH_TTS_CHARS,
            "free_max_document_size_bytes": FREE_MAX_FILE_SIZE,
            "free_max_message_characters": MAX_MESSAGE_CHARS,
            "free_daily_ai_budget_usd": FREE_DAILY_AI_BUDGET_USD,
            "account_creation": f"{MAX_ACCOUNTS_PER_HOUR} per IP per hour",
            "messages_per_user_per_hour": MAX_MESSAGES_PER_HOUR,
            "failed_logins_per_ip_per_hour": MAX_FAILED_LOGINS_PER_HOUR,
            "creator_exemption": "Unlimited for the canonical creator account"
        },
        "security": {
            "password_hashing": "bcrypt",
            "sessions": "Server-generated cryptographic tokens",
            "session_expiry": f"{SESSION_EXPIRY_DAYS} days",
            "cors": "Restricted (no wildcard)",
            "creator_file_size_limit": f"{MAX_FILE_SIZE // (1024*1024)}MB",
            "free_file_size_limit": f"{FREE_MAX_FILE_SIZE // (1024*1024)}MB",
            "brute_force_protection": f"{MAX_FAILED_LOGINS_PER_HOUR} attempts per hour"
        },
        "control_center": "https://sanctumly.space/admin/ai-control",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
