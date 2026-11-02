"""Provider-specific aggregation helpers for AI telemetry."""
from sqlalchemy import func

from app.models.ai_routing_event import AIRoutingEvent


def groq_text_cost_total(db, since) -> float:
    """Return Groq text-inference cost only (exclude other providers/vision)."""
    value = db.query(
        func.coalesce(func.sum(AIRoutingEvent.estimated_cost_usd), 0.0)
    ).filter(
        AIRoutingEvent.created_at >= since,
        AIRoutingEvent.provider == "groq",
        AIRoutingEvent.routing_reason != "vision_request",
    ).scalar()
    return float(value or 0.0)
