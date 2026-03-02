"""
Therapist Knowledge Base model
Professional therapeutic content curated by licensed therapists
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from datetime import datetime
from app.database import Base


class TherapistKnowledge(Base):
    """Curated therapeutic knowledge from licensed professionals"""
    __tablename__ = 'therapist_knowledge'
    
    id = Column(Integer, primary_key=True)
    category = Column(String(100), nullable=False)  # e.g. 'CBT', 'grief', 'anxiety', 'depression', 'relationships'
    title = Column(String(500), nullable=False)       # Short title for admin listing
    content = Column(Text, nullable=False)            # The actual therapeutic guidance
    author = Column(String(200))                      # Therapist name/credential
    is_active = Column(Boolean, default=True)         # Can be toggled on/off without deleting
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

