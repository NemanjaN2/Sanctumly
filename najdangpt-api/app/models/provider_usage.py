"""Provider-wide usage ledger shared by every Sanctumly account."""
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text, UniqueConstraint, Index
from app.database import Base


class ProviderDailyUsage(Base):
    __tablename__ = "provider_daily_usage"
    __table_args__ = (
        UniqueConstraint("provider", "usage_date", name="uq_provider_daily_usage_provider_date"),
        Index("ix_provider_daily_usage_date", "usage_date"),
    )

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)
    usage_date = Column(Date, nullable=False)
    used_neurons = Column(Float, nullable=False, default=0.0)
    reserved_neurons = Column(Float, nullable=False, default=0.0)
    status = Column(String(20), nullable=False, default="available")
    last_error = Column(Text)
    cooldown_until = Column(DateTime)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
