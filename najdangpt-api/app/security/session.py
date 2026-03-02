"""
Secure session management
"""

import secrets
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.config import SESSION_EXPIRY_DAYS
from app.models.account import UserSession

logger = logging.getLogger(__name__)


def generate_session_id(username: str) -> str:
    """Generate cryptographically secure session ID"""
    random_part = secrets.token_urlsafe(32)
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    return f"session_{username}_{timestamp}_{random_part}"


def verify_session_ownership_flexible(session_id: str, username: str, db: Session) -> bool:
    """
    STRICT SESSION VERIFICATION
    Only accepts secure server-generated sessions.
    Legacy sessions are rejected - users must re-login.
    """
    # Try to find secure session in database
    session = db.query(UserSession).filter_by(
        session_id=session_id,
        username=username.lower()
    ).first()
    
    if session:
        # Secure session found - update last used time
        session.last_used = datetime.utcnow()
        db.commit()
        logger.info(f"✅ Secure session verified: {username}")
        return True
    
    # No secure session found - REJECT (force re-login)
    logger.warning(f"🚫 REJECTED: {username} using invalid/legacy session {session_id[:30]}...")
    return False


def cleanup_expired_sessions(db: Session):
    """Remove sessions older than SESSION_EXPIRY_DAYS"""
    try:
        expiry_date = datetime.utcnow() - timedelta(days=SESSION_EXPIRY_DAYS)
        
        deleted = db.query(UserSession).filter(
            UserSession.last_used < expiry_date
        ).delete()
        
        db.commit()
        
        if deleted > 0:
            logger.info(f"🧹 Cleaned up {deleted} expired sessions")
    except Exception as e:
        logger.error(f"❌ Session cleanup error: {e}")
        db.rollback()
