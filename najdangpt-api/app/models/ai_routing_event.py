"""Privacy-minimal audit events for adaptive model routing.

No prompts, completions, usernames, session IDs, or credentials are stored.
"""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String
from app.database import Base


class AIRoutingEvent(Base):
    __tablename__ = "ai_routing_events"
    __table_args__ = (
        Index("ix_ai_routing_events_created_at", "created_at"),
        Index("ix_ai_routing_events_provider_created", "provider", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    provider = Column(String(40), nullable=False)
    model = Column(String(160), nullable=False, default="")
    routing_reason = Column(String(80), nullable=False, default="unknown")
    fallback_used = Column(Boolean, nullable=False, default=False)
    success = Column(Boolean, nullable=False, default=True)
    account_type = Column(String(20), nullable=False, default="standard")
    latency_ms = Column(Integer, nullable=False, default=0)
    neurons_used = Column(Float)
    error_type = Column(String(120))
