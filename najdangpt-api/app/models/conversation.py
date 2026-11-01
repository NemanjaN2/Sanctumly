"""Conversation ownership independent of login/authentication sessions.

Native clients may use their server-issued login session as a conversation ID;
the web client uses a separate local conversation ID. This table binds either
kind of conversation identifier to exactly one account without changing the
existing message/document API contract.
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, String, Index
from app.database import Base


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"
    __table_args__ = (
        Index("ix_conversation_sessions_username", "username"),
        Index("ix_conversation_sessions_last_used", "last_used"),
    )

    session_id = Column(String(100), primary_key=True)
    username = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=False, default=datetime.utcnow)
