"""
Conversation memory routes

SECURITY: The caller is identified by their session token, and may only
read/write THEIR OWN memory. The username in the path/query must match the
authenticated account (or the caller must be a creator).
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.security import validate_username, require_user
from app.models.account import Account
from app.services.memory import get_conversation_memory, update_conversation_memory
from app.security.usage import is_creator_account

router = APIRouter(prefix="/memory", tags=["Memory"])

class MemoryUpdateRequest(BaseModel):
    username: str
    summary: str = Field(default="", max_length=5000)
    key_facts: str = Field(default="", max_length=5000)
    preferences: str = Field(default="", max_length=3000)



def _authorize_target(account: Account, username: str):
    """Allow only self-access, unless the caller is a creator."""
    if is_creator_account(account):
        return
    if account.username.lower() != username.lower():
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/update")
async def update_memory(
    username: str | None = None,
    summary: str = "",
    key_facts: str = "",
    preferences: str = "",
    payload: MemoryUpdateRequest | None = Body(default=None),
    account: Account = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Update user memory (self only); accepts legacy query and JSON payloads."""
    if payload is not None:
        username = payload.username
        summary = payload.summary
        key_facts = payload.key_facts
        preferences = payload.preferences
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
    if max(len(summary), len(key_facts), len(preferences)) > 5000 or len(preferences) > 3000:
        raise HTTPException(status_code=413, detail="Memory fields exceed the allowed size")
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
