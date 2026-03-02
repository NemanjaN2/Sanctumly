"""
Conversation memory routes
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import validate_username
from app.services.memory import get_conversation_memory, update_conversation_memory

router = APIRouter(prefix="/memory", tags=["Memory"])


@router.post("/update")
async def update_memory(
    username: str,
    summary: str = "",
    key_facts: str = "",
    preferences: str = "",
    db: Session = Depends(get_db)
):
    """Update user memory"""
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
    
    update_conversation_memory(username, summary, key_facts, preferences, db)
    return {"success": True, "message": "Memory updated"}


@router.get("/{username}")
async def get_memory(username: str, db: Session = Depends(get_db)):
    """Get user memory"""
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
    
    memory = get_conversation_memory(username, db)
    return memory or {"summary": "", "key_facts": "", "preferences": ""}
