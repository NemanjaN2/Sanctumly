"""
app/security/dependencies.py

Real authentication gates for protected endpoints.

Every protected route Depends() on one of these instead of trusting a username
passed in the request body/query. The caller must send their session token
(issued at login) in the Authorization header:

    Authorization: Bearer session_<username>_<ts>_<random>

Usage:
    from app.security.dependencies import require_user, require_creator

    @router.get("/admin/messages")
    async def get_messages(account: Account = Depends(require_creator), ...):
        ...  # account is guaranteed to be a real, authenticated creator
"""

import logging
from datetime import datetime
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account, UserSession

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


def require_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Account:
    """
    Resolve and verify the caller from their session token.
    Returns the authenticated Account or raises 401.

    This is the ONLY trustworthy source of "who is calling" — never trust a
    username from the request body.
    """
    token = _extract_token(authorization)

    session = db.query(UserSession).filter_by(session_id=token).first()
    if not session:
        logger.warning("🚫 Auth failed: unknown session token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    account = db.query(Account).filter_by(username=session.username).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    # Touch last_used so active sessions don't get reaped
    session.last_used = datetime.utcnow()
    db.commit()

    return account


def require_creator(account: Account = Depends(require_user)) -> Account:
    """Require the authenticated caller to be a creator."""
    if not account.is_creator:
        logger.warning(f"🚫 Non-creator '{account.username}' attempted a creator-only action")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Creator only")
    return account


def require_admin(account: Account = Depends(require_user)) -> Account:
    """Require the authenticated caller to be an admin (or creator)."""
    if not (account.is_admin or account.is_creator):
        logger.warning(f"🚫 Non-admin '{account.username}' attempted an admin-only action")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return account
