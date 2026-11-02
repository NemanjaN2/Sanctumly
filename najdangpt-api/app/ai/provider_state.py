"""Database-backed provider-wide quota and circuit-breaker state.

Unlike DailyUsage, this ledger is intentionally NOT keyed by username. All
Sanctumly users consume the same Cloudflare account-level Neuron allowance.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import (
    CLOUDFLARE_DAILY_NEURON_BUDGET,
    CLOUDFLARE_FAILURE_COOLDOWN_SECONDS,
)
from app.models.provider_usage import ProviderDailyUsage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NeuronReservation:
    provider: str
    usage_date: date
    amount: float


def utc_today() -> date:
    return datetime.utcnow().date()


def _get_locked_row(db: Session, provider: str) -> ProviderDailyUsage:
    today = utc_today()
    row = db.query(ProviderDailyUsage).filter_by(
        provider=provider, usage_date=today
    ).first()
    if row is None:
        db.add(ProviderDailyUsage(provider=provider, usage_date=today))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    row = db.query(ProviderDailyUsage).filter_by(
        provider=provider, usage_date=today
    ).with_for_update().first()
    if row is None:
        raise RuntimeError("Unable to initialize provider usage ledger")
    return row


def reserve_cloudflare_neurons(db: Session, estimated_neurons: float) -> NeuronReservation | None:
    """Reserve estimated Neurons atomically before calling Cloudflare.

    A 1,000-Neuron buffer is retained by default: Sanctumly stops routing to
    Qwen at 9,000 of the documented 10,000 daily free Neurons. The threshold
    is configurable in Railway. Provider-side quota errors still trip the
    circuit breaker immediately.
    """
    amount = max(1.0, float(estimated_neurons))
    row = _get_locked_row(db, "cloudflare")
    now = datetime.utcnow()

    if row.status == "exhausted":
        return None
    if row.cooldown_until and row.cooldown_until > now:
        return None
    if row.status in {"cooldown", "unavailable"}:
        row.status = "available"
        row.cooldown_until = None

    committed_and_reserved = float(row.used_neurons or 0.0) + float(row.reserved_neurons or 0.0)
    if committed_and_reserved + amount > CLOUDFLARE_DAILY_NEURON_BUDGET:
        row.status = "exhausted"
        row.last_error = (
            f"Sanctumly safety threshold reached: {committed_and_reserved:.2f} "
            f"used/reserved of {CLOUDFLARE_DAILY_NEURON_BUDGET:.2f} Neurons"
        )
        row.updated_at = now
        db.commit()
        logger.warning("Cloudflare daily Neuron safety threshold reached; routing to fallback")
        return None

    row.reserved_neurons = float(row.reserved_neurons or 0.0) + amount
    row.updated_at = now
    db.commit()
    return NeuronReservation("cloudflare", row.usage_date, amount)


def settle_cloudflare_neurons(
    db: Session,
    reservation: NeuronReservation | None,
    actual_neurons: float | None,
) -> None:
    """Release a reservation and add measured usage (or the safe estimate)."""
    if reservation is None:
        return
    row = db.query(ProviderDailyUsage).filter_by(
        provider=reservation.provider,
        usage_date=reservation.usage_date,
    ).with_for_update().first()
    if row is None:
        return

    row.reserved_neurons = max(
        0.0, float(row.reserved_neurons or 0.0) - reservation.amount
    )
    # If Cloudflare omits usage.neurons, conservatively account for the full
    # reservation instead of pretending that the request consumed zero.
    measured = reservation.amount if actual_neurons is None else max(0.0, float(actual_neurons))
    row.used_neurons = float(row.used_neurons or 0.0) + measured
    if row.used_neurons >= CLOUDFLARE_DAILY_NEURON_BUDGET:
        row.status = "exhausted"
    row.updated_at = datetime.utcnow()
    db.commit()


def release_cloudflare_reservation(
    db: Session,
    reservation: NeuronReservation | None,
    *,
    exhausted: bool = False,
    error: str | None = None,
    cooldown_seconds: int | None = None,
) -> None:
    """Release an in-flight reservation and update shared provider state."""
    if reservation is None:
        return
    row = db.query(ProviderDailyUsage).filter_by(
        provider=reservation.provider,
        usage_date=reservation.usage_date,
    ).with_for_update().first()
    if row is None:
        return
    row.reserved_neurons = max(
        0.0, float(row.reserved_neurons or 0.0) - reservation.amount
    )
    if exhausted:
        row.status = "exhausted"
        row.cooldown_until = None
    elif cooldown_seconds is not None:
        row.status = "cooldown"
        row.cooldown_until = datetime.utcnow() + timedelta(seconds=max(1, cooldown_seconds))
    row.last_error = (error or "")[:2000] or row.last_error
    row.updated_at = datetime.utcnow()
    db.commit()


def cloudflare_provider_snapshot(db: Session) -> dict:
    row = db.query(ProviderDailyUsage).filter_by(
        provider="cloudflare", usage_date=utc_today()
    ).first()
    used = float(row.used_neurons or 0.0) if row else 0.0
    reserved = float(row.reserved_neurons or 0.0) if row else 0.0
    status = row.status if row else "available"
    if row and row.cooldown_until and row.cooldown_until <= datetime.utcnow() and status == "cooldown":
        status = "available"
    return {
        "provider": "cloudflare",
        "status": status,
        "used_neurons": round(used, 3),
        "reserved_neurons": round(reserved, 3),
        "sanctumly_neuron_budget": CLOUDFLARE_DAILY_NEURON_BUDGET,
        "remaining_estimate": round(max(0.0, CLOUDFLARE_DAILY_NEURON_BUDGET - used - reserved), 3),
        "usage_date_utc": utc_today().isoformat(),
        "reset_at_utc": f"{(utc_today() + timedelta(days=1)).isoformat()}T00:00:00Z",
        "last_error": row.last_error if row else None,
    }


def mark_cloudflare_exhausted(db: Session, error: str) -> None:
    """Trip the daily circuit breaker after a provider quota-exhaustion error."""
    row = _get_locked_row(db, "cloudflare")
    row.status = "exhausted"
    row.last_error = (error or "Cloudflare daily quota exhausted")[:2000]
    row.cooldown_until = None
    row.updated_at = datetime.utcnow()
    db.commit()
    logger.warning("Cloudflare marked exhausted for UTC day; all accounts will use fallback")


def mark_cloudflare_unavailable(db: Session, error: str) -> None:
    """Apply a short shared cooldown after a transient provider failure."""
    row = _get_locked_row(db, "cloudflare")
    row.status = "cooldown"
    row.last_error = (error or "Cloudflare temporarily unavailable")[:2000]
    row.cooldown_until = datetime.utcnow() + timedelta(seconds=CLOUDFLARE_FAILURE_COOLDOWN_SECONDS)
    row.updated_at = datetime.utcnow()
    db.commit()
