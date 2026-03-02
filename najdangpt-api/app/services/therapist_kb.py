"""
Therapist Knowledge retrieval service
Add this function to app/services/__init__.py or create app/services/therapist_kb.py
"""

from sqlalchemy.orm import Session
from app.models.therapist_knowledge import TherapistKnowledge


def get_therapist_knowledge_context(db: Session, max_entries: int = 10) -> str:
    """
    Retrieve active therapist knowledge to inject into wellness mode context.
    Returns formatted string for system prompt injection.
    """
    entries = db.query(TherapistKnowledge).filter_by(
        is_active=True
    ).order_by(TherapistKnowledge.category).limit(max_entries).all()
    
    if not entries:
        return ""
    
    parts = []
    current_category = None
    
    for entry in entries:
        if entry.category != current_category:
            current_category = entry.category
            parts.append(f"\n[{entry.category.upper()}]")
        parts.append(f"{entry.title}: {entry.content}")
    
    return "\n".join(parts)
