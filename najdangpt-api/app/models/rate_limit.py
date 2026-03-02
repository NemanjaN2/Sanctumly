"""
Rate limiting and settings models
"""

from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.database import Base


class MessageRateLimit(Base):
    """Track message requests per user for rate limiting"""
    __tablename__ = 'message_rate_limit'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100))
    timestamp = Column(DateTime, default=datetime.utcnow)


class AccountCreationLog(Base):
    """Track account creation per IP for rate limiting"""
    __tablename__ = 'account_creation_log'
    
    id = Column(Integer, primary_key=True)
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)


class Settings(Base):
    """Application settings storage"""
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)
