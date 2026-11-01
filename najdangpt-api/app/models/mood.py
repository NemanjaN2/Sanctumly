"""
Mood tracking model
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from datetime import datetime
from app.database import Base

class MoodEntry(Base):
    """Daily mood check-in"""
    __tablename__ = 'mood_entries'
    __table_args__ = (Index('ix_mood_entries_username_timestamp', 'username', 'timestamp'),)
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    mood_score = Column(Integer, nullable=False)  # 1-5
    emoji = Column(String(10))
    note = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
