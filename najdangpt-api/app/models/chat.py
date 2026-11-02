"""
Chat-related database models
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from datetime import datetime
from app.database import Base


class Message(Base):
    """Chat message model"""
    __tablename__ = 'messages'
    __table_args__ = (
        Index('ix_messages_session_timestamp', 'session_id', 'timestamp'),
        Index('ix_messages_username_timestamp', 'username', 'timestamp'),
    )
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100))
    username = Column(String(100))
    role = Column(String(20))  # 'user' or 'assistant'
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)


class MessageFeedback(Base):
    """User feedback on AI responses"""
    __tablename__ = 'message_feedback'
    __table_args__ = (Index('ix_message_feedback_username_timestamp', 'username', 'timestamp'),)
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100))
    username = Column(String(100))
    message_content = Column(Text)
    feedback_type = Column(String(20))  # 'like' or 'dislike'
    timestamp = Column(DateTime, default=datetime.utcnow)
