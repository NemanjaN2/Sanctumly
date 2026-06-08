"""
Sanctumly FastAPI Backend - v8.0.0 Modular Architecture
Clean, organized, production-ready
"""

import logging
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    ALLOWED_ORIGINS,
    SUPPORTED_FILE_TYPES,
    MAX_FILE_SIZE,
    SESSION_EXPIRY_DAYS,
)
from app.database import init_db, SessionLocal
from app.models.account import Account
from app.security import hash_password, cleanup_old_rate_limit_logs, cleanup_expired_sessions
from app.routers import auth, chat, upload, memory, feedback, admin, speech, mood

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Sanctumly API",
    description="Your AI Companion - Modular Architecture",
    version="8.0.0"
)

ALLOWED_ORIGINS = [
    "https://sanctumly.space",
    "https://www.sanctumly.space",
    "https://najdangpt.space",
    "https://www.najdangpt.space",
    "http://localhost:3000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


def initialize_father_account(db):
    """Ensure Father's account exists with bcrypt password"""
    father = db.query(Account).filter_by(username='father').first()
    
    if not father:
        father = Account(
            username='father',
            password_hash=hash_password('#Blessed2!'),
            is_admin=True,
            is_creator=True
        )
        db.add(father)
        db.commit()
        logger.info("✅ Created Father's account (bcrypt)")
    else:
        if not father.password_hash.startswith('$2'):
            father.password_hash = hash_password('#Blessed2!')
            db.commit()
            logger.info("✅ Updated Father's password to bcrypt")
        father.is_admin = True
        father.is_creator = True
        db.commit()
        logger.info("✅ Father's account verified")


@app.on_event("startup")
async def startup_event():
    """Initialize database and run startup tasks"""
    init_db()
    
    db = SessionLocal()
    try:
        initialize_father_account(db)
        cleanup_old_rate_limit_logs(db)
        cleanup_expired_sessions(db)
        logger.info("🚀 Sanctumly API v8.0.0 - Modular Architecture")
        logger.info("🔒 Security: bcrypt passwords, secure sessions, no CORS wildcard")
    finally:
        db.close()


@app.get("/")
async def root():
    """API info endpoint"""
    return {
        "app": "Sanctumly API",
        "version": "8.0.0",
        "architecture": "Modular",
        "ai_engine": "Groq (Llama 3.3 70B)",
        "features": [
            "Secure Sessions (server-generated)",
            "bcrypt Password Hashing",
            "RAG (Document Analysis)",
            "Conversation Memory",
            "Creator Mode",
            "Multi-File Support",
            "Rate Limiting",
            "Web Search"
        ],
        "supported_files": SUPPORTED_FILE_TYPES,
        "rate_limits": {
            "account_creation": "3 per IP per hour",
            "messages": "30 per user per hour",
            "creator_exemption": "Unlimited"
        },
        "security": {
            "password_hashing": "bcrypt",
            "sessions": "Server-generated cryptographic tokens",
            "session_expiry": f"{SESSION_EXPIRY_DAYS} days",
            "cors": "Restricted (no wildcard)",
            "file_size_limit": f"{MAX_FILE_SIZE // (1024*1024)}MB",
            "brute_force_protection": "10 attempts per hour"
        },
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
