"""
Account-related database models
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from app.database import Base


class Account(Base):
    """User account model"""
    __tablename__ = 'accounts'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255))
    is_admin = Column(Boolean, default=False)
    is_creator = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)


class UserSession(Base):
    """Secure session management"""
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100), unique=True, nullable=False)
    username = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    is_secure = Column(Boolean, default=True)


class FailedLoginAttempt(Base):
    """Track failed login attempts for security"""
    __tablename__ = 'failed_login_attempts'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100))
    ip_address = Column(String(50))
    timestamp = Column(DateTime, default=datetime.utcnow)
    attempt_type = Column(String(20))  # 'login' or 'signup'
