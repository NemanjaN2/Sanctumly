"""
app/security/dependencies.py

Real authentication gates for protected endpoints.

Every protected route Depends() on one of these instead of trusting a username
passed in the request body/query. The caller must send their session token
(issued at login) in the Authorization header:

    Authorization: Bearer an opaque server-generated session token

Usage:
    from app.security.dependencies import require_user, require_creator

    @router.get("/admin/messages")
    async def get_messages(account: Account = Depends(require_creator), ...):
        ...  # account is guaranteed to be a real, authenticated creator
"""

import logging
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account, UserSession
from app.config import SESSION_EXPIRY_DAYS
from app.security.session import find_session_by_token

logger = logging.getLogger(__name__)


def _extract_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()  # also accept a bare token


def authenticate_session_token(token: str, db: Session, touch: bool = True) -> Account:
    """Validate a server-issued session token and return its owning account."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session = find_session_by_token(token, db)
    if not session:
        logger.warning("Auth failed: unknown session token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session_activity = session.last_used or session.created_at
    if session_activity and session_activity < datetime.utcnow() - timedelta(days=SESSION_EXPIRY_DAYS):
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    account = db.query(Account).filter_by(username=session.username).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    if touch:
        session.last_used = datetime.utcnow()
        db.commit()
    return account


def extract_bearer_token(authorization: str | None) -> str:
    return _extract_token(authorization)


def require_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Account:
    """Resolve the caller only from a valid server-issued Bearer session."""
    return authenticate_session_token(_extract_token(authorization), db)


def require_creator(account: Account = Depends(require_user)) -> Account:
    """Require the authenticated caller to be a creator."""
    if not (account.is_creator and account.username.lower() == "father"):
        logger.warning(f"🚫 Non-creator '{account.username}' attempted a creator-only action")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Creator only")
    return account


def require_admin(account: Account = Depends(require_user)) -> Account:
    """Require the authenticated caller to be an admin (or creator)."""
    if not (account.is_admin or (account.is_creator and account.username.lower() == "father")):
        logger.warning(f"🚫 Non-admin '{account.username}' attempted an admin-only action")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return account
