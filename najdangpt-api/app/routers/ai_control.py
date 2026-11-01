"""Creator-only AI Control Center API.

The frontend is served by the Sanctumly Vercel app. This router exposes only
aggregated, prompt-free telemetry and a temporary global provider override.
"""
import logging
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai.control import get_provider_override, set_provider_override
from app.ai.provider_state import cloudflare_provider_snapshot, utc_today
from app.config import (
    CLOUDFLARE_ACCOUNT_ID,
    CLOUDFLARE_API_TOKEN,
    CLOUDFLARE_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    SERPER_API_KEY,
)
from app.database import get_db
from app.models.ai_routing_event import AIRoutingEvent
from app.models.usage import DailyUsage
from app.security import require_creator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/ai-control", tags=["AI Control Center"])


class ProviderOverrideRequest(BaseModel):
    mode: Literal["auto", "groq"]
    duration_minutes: int = Field(default=60, ge=15, le=1440)


@router.get("/overview")
async def ai_control_overview(
    days: int = Query(default=7, ge=1, le=30),
    _creator=Depends(require_creator),
    db: Session = Depends(get_db),
):
    """Aggregated provider health and routing analytics; no prompts or PII."""
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    today = utc_today()
    day_start = datetime.combine(today, datetime.min.time())

    cloudflare = cloudflare_provider_snapshot(db)
    configured_cloudflare = bool(CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN)

    total = db.query(func.count(AIRoutingEvent.id)).filter(
        AIRoutingEvent.created_at >= since
    ).scalar() or 0
    successful = db.query(func.count(AIRoutingEvent.id)).filter(
        AIRoutingEvent.created_at >= since,
        AIRoutingEvent.success.is_(True),
    ).scalar() or 0
    failed = total - successful
    fallback_count = db.query(func.count(AIRoutingEvent.id)).filter(
        AIRoutingEvent.created_at >= since,
        AIRoutingEvent.fallback_used.is_(True),
    ).scalar() or 0
    avg_latency = db.query(func.avg(AIRoutingEvent.latency_ms)).filter(
        AIRoutingEvent.created_at >= since,
        AIRoutingEvent.success.is_(True),
    ).scalar()

    provider_rows = db.query(
        AIRoutingEvent.provider, func.count(AIRoutingEvent.id)
    ).filter(AIRoutingEvent.created_at >= since).group_by(AIRoutingEvent.provider).all()
    reason_rows = db.query(
        AIRoutingEvent.routing_reason, func.count(AIRoutingEvent.id)
    ).filter(AIRoutingEvent.created_at >= since).group_by(AIRoutingEvent.routing_reason).all()
    account_rows = db.query(
        AIRoutingEvent.account_type, func.count(AIRoutingEvent.id)
    ).filter(AIRoutingEvent.created_at >= since).group_by(AIRoutingEvent.account_type).all()

    search_count = db.query(func.coalesce(func.sum(DailyUsage.web_searches), 0)).filter(
        DailyUsage.usage_date == today
    ).scalar() or 0
    text_count_today = db.query(func.count(AIRoutingEvent.id)).filter(
        AIRoutingEvent.created_at >= day_start
    ).scalar() or 0

    # This is an observation from the latest recorded request, not an active
    # health probe. The UI labels it accordingly to avoid overstating health.
    latest_groq_event = db.query(AIRoutingEvent).filter(
        AIRoutingEvent.provider == "groq"
    ).order_by(AIRoutingEvent.created_at.desc()).first()
    if not GROQ_API_KEY:
        groq_health = "not_configured"
    elif latest_groq_event is None:
        groq_health = "unknown"
    else:
        groq_health = "available" if latest_groq_event.success else "degraded"

    recent = db.query(AIRoutingEvent).filter(
        AIRoutingEvent.created_at >= since
    ).order_by(AIRoutingEvent.created_at.desc()).limit(20).all()
    events = [
        {
            "timestamp": item.created_at.isoformat() + "Z",
            "provider": item.provider,
            "model": item.model,
            "reason": item.routing_reason,
            "fallback": bool(item.fallback_used),
            "success": bool(item.success),
            "account_type": item.account_type,
            "latency_ms": item.latency_ms,
            "neurons_used": item.neurons_used,
            "error_type": item.error_type,
        }
        for item in recent
    ]

    override = get_provider_override(db)
    return {
        "generated_at": now.isoformat() + "Z",
        "period_days": days,
        "providers": {
            "cloudflare": {
                **cloudflare,
                "configured": configured_cloudflare,
                "model": CLOUDFLARE_MODEL,
                "health": cloudflare["status"] if configured_cloudflare else "not_configured",
            },
            "groq": {
                "configured": bool(GROQ_API_KEY),
                "model": GROQ_MODEL,
                "health": groq_health,
                "last_event_at": (
                    latest_groq_event.created_at.isoformat() + "Z"
                    if latest_groq_event else None
                ),
            },
            "serper": {
                "configured": bool(SERPER_API_KEY),
                "health": "configured" if SERPER_API_KEY else "not_configured",
                "searches_today": int(search_count),
            },
        },
        "metrics": {
            "requests": int(total),
            "successful_requests": int(successful),
            "failed_requests": int(failed),
            "fallback_events": int(fallback_count),
            "average_latency_ms": round(float(avg_latency), 1) if avg_latency is not None else None,
            "success_rate_percent": round((successful / total) * 100, 1) if total else None,
            "text_requests_today": int(text_count_today),
            "web_searches_today": int(search_count),
            "provider_distribution": {str(k): int(v) for k, v in provider_rows},
            "routing_reasons": {str(k): int(v) for k, v in reason_rows},
            "account_distribution": {str(k): int(v) for k, v in account_rows},
        },
        "override": override,
        "quota_scope": "shared_by_all_sanctumly_accounts",
        "recent_events": events,
    }


@router.put("/override")
async def update_ai_provider_override(
    payload: ProviderOverrideRequest,
    creator=Depends(require_creator),
    db: Session = Depends(get_db),
):
    """Temporarily force GPT-OSS or return routing to automatic mode."""
    if payload.mode == "groq" and not GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="Groq is not configured")
    try:
        state = set_provider_override(
            db,
            payload.mode,
            payload.duration_minutes,
            updated_by=creator.username.lower(),
        )
    except Exception:
        db.rollback()
        logger.exception("AI provider override update failed")
        raise HTTPException(status_code=500, detail="Could not update provider override")
    logger.warning("Creator changed AI provider override to %s", payload.mode)
    return {"success": True, "override": state}
