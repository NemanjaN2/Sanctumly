"""Secure server-side session token management."""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import SESSION_EXPIRY_DAYS
from app.models.account import UserSession

logger = logging.getLogger(__name__)
SESSION_TOKEN_HASH_PREFIX = "sha256:"


def hash_session_token(raw_token: str) -> str:
    """Return a one-way digest for a high-entropy server-issued bearer token."""
    token = (raw_token or "").strip()
    return SESSION_TOKEN_HASH_PREFIX + hashlib.sha256(token.encode("utf-8")).hexdigest()


def find_session_by_token(raw_token: str, db: Session) -> UserSession | None:
    """Find a session by its raw client token while storing only its digest.

    The plaintext lookup is a one-time rolling compatibility path for rows
    created by older backend versions. A matched legacy row is re-hashed in
    place, without changing the token already held by iOS, Android or web.
    """
    token = (raw_token or "").strip()
    if not token:
        return None

    digest = hash_session_token(token)
    session = db.query(UserSession).filter_by(session_id=digest).first()
    if session:
        return session

    legacy = db.query(UserSession).filter_by(session_id=token).first()
    if not legacy:
        return None

    legacy.session_id = digest
    try:
        db.commit()
        return legacy
    except IntegrityError:
        db.rollback()
        return db.query(UserSession).filter_by(session_id=digest).first()


def migrate_legacy_session_tokens(db: Session) -> int:
    """Hash all pre-9.0 plaintext session IDs in place; return migrated rows."""
    rows = db.query(UserSession).all()
    migrated = 0
    for session in rows:
        current = session.session_id or ""
        if current.startswith(SESSION_TOKEN_HASH_PREFIX):
            continue
        session.session_id = hash_session_token(current)
        migrated += 1

    if migrated:
        try:
            db.commit()
            logger.info("Re-hashed %s legacy session tokens at rest", migrated)
        except IntegrityError:
            db.rollback()
            raise
    return migrated


def generate_session_id(username: str) -> str:
    """Generate a cryptographically secure opaque session ID for client use."""
    random_part = secrets.token_urlsafe(32)
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    # The username is intentionally not embedded: the account association is
    # stored server-side, and max-length usernames must not overflow columns.
    return f"session_{timestamp}_{random_part}"


def verify_session_ownership_flexible(session_id: str, username: str, db: Session) -> bool:
    """Verify a server-issued session when legacy mobile clients omit Bearer auth."""
    session = find_session_by_token(session_id, db)
    if session and session.username.lower() == username.lower():
        session_activity = session.last_used or session.created_at
        if session_activity and session_activity < datetime.utcnow() - timedelta(days=SESSION_EXPIRY_DAYS):
            db.delete(session)
            db.commit()
            logger.info("Expired session rejected for %s", username)
            return False
        session.last_used = datetime.utcnow()
        db.commit()
        logger.info("Secure session verified for %s", username)
        return True

    logger.warning("Rejected invalid or legacy session for %s", username)
    return False


def cleanup_expired_sessions(db: Session):
    """Remove sessions older than SESSION_EXPIRY_DAYS."""
    try:
        expiry_date = datetime.utcnow() - timedelta(days=SESSION_EXPIRY_DAYS)
        deleted = db.query(UserSession).filter(
            UserSession.last_used < expiry_date
        ).delete()
        db.commit()
        if deleted > 0:
            logger.info("Cleaned up %s expired sessions", deleted)
    except Exception:
        logger.exception("Session cleanup failed")
        db.rollback()
