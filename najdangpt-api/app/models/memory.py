"""
Conversation memory for long-term user context
"""

from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.database import Base


class ConversationMemory(Base):
    """Long-term memory about users"""
    __tablename__ = 'conversation_memory'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), unique=True)
    summary = Column(Text)
    key_facts = Column(Text)
    preferences = Column(Text)
    last_updated = Column(DateTime, default=datetime.utcnow)
