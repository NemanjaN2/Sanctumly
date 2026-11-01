"""
Document storage for RAG system
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from datetime import datetime
from app.database import Base


class UserDocument(Base):
    """Uploaded document chunks with embeddings for RAG"""
    __tablename__ = 'user_documents'
    __table_args__ = (Index('ix_user_documents_session_chunk', 'session_id', 'chunk_index'),)
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100))
    filename = Column(String(500))
    chunk_index = Column(Integer, default=0)
    content = Column(Text)
    embedding = Column(Text, nullable=True)  # JSON-encoded embedding vector
    upload_date = Column(DateTime, default=datetime.utcnow)
