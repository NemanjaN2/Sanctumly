"""
Conversation memory routes

SECURITY: The caller is identified by their session token, and may only
read/write THEIR OWN memory. The username in the path/query must match the
authenticated account (or the caller must be a creator).
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import validate_username, require_user
from app.models.account import Account
from app.services.memory import get_conversation_memory, update_conversation_memory

router = APIRouter(prefix="/memory", tags=["Memory"])


def _authorize_target(account: Account, username: str):
    """Allow only self-access, unless the caller is a creator."""
    if account.is_creator:
        return
    if account.username.lower() != username.lower():
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/update")
async def update_memory(
    username: str,
    summary: str = "",
    key_facts: str = "",
    preferences: str = "",
    account: Account = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Update user memory (self only)."""
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
    _authorize_target(account, username)

    update_conversation_memory(username, summary, key_facts, preferences, db)
    return {"success": True, "message": "Memory updated"}


@router.get("/{username}")
async def get_memory(
    username: str,
    account: Account = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Get user memory (self only)."""
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
    _authorize_target(account, username)

    memory = get_conversation_memory(username, db)
    return memory or {"summary": "", "key_facts": "", "preferences": ""}
