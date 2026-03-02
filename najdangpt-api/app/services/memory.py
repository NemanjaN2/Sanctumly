"""
Conversation memory service
Long-term user context and preferences
"""

from datetime import datetime
from sqlalchemy.orm import Session
from app.models.memory import ConversationMemory


def get_conversation_memory(username: str, db: Session) -> dict | None:
    """Get user's conversation memory"""
    memory = db.query(ConversationMemory).filter_by(user_id=username.lower()).first()
    if memory:
        return {
            "summary": memory.summary or "",
            "key_facts": memory.key_facts or "",
            "preferences": memory.preferences or ""
        }
    return None


def update_conversation_memory(username: str, summary: str, key_facts: str, preferences: str, db: Session):
    """Update user's conversation memory"""
    memory = db.query(ConversationMemory).filter_by(user_id=username.lower()).first()
    
    if memory:
        memory.summary = summary
        memory.key_facts = key_facts
        memory.preferences = preferences
        memory.last_updated = datetime.utcnow()
    else:
        memory = ConversationMemory(
            user_id=username.lower(),
            summary=summary,
            key_facts=key_facts,
            preferences=preferences
        )
        db.add(memory)
    
    db.commit()
