"""Daily, per-account usage counters and estimated provider spend."""
from datetime import date, datetime
from sqlalchemy import Column, Date, DateTime, Float, Integer, String, UniqueConstraint, Index
from app.database import Base


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (
        UniqueConstraint("username", "usage_date", name="uq_daily_usage_username_date"),
        Index("ix_daily_usage_date", "usage_date"),
    )

    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    usage_date = Column(Date, nullable=False, default=date.today)
    text_requests = Column(Integer, nullable=False, default=0)
    image_analyses = Column(Integer, nullable=False, default=0)
    web_searches = Column(Integer, nullable=False, default=0)
    document_uploads = Column(Integer, nullable=False, default=0)
    transcription_seconds = Column(Float, nullable=False, default=0.0)
    english_tts_characters = Column(Integer, nullable=False, default=0)
    estimated_cost_usd = Column(Float, nullable=False, default=0.0)
    reserved_cost_usd = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
