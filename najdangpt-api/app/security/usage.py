"""Central free-tier quota and estimated AI spend enforcement.

Free-plan counters are stored per user and UTC calendar day. PostgreSQL row
locks serialize concurrent requests for the same account/day. Creator (father)
is explicitly exempt from all quota and budget enforcement. Creator provider
spend is still recorded for cost visibility, without blocking requests.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import logging
import math
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.config import (
    FREE_DAILY_TEXT_REQUESTS, FREE_DAILY_IMAGE_ANALYSES, FREE_DAILY_WEB_SEARCHES,
    FREE_DAILY_DOCUMENT_UPLOADS, FREE_DAILY_TRANSCRIPTION_SECONDS,
    FREE_DAILY_ENGLISH_TTS_CHARS, FREE_DAILY_AI_BUDGET_USD,
    GROQ_TEXT_INPUT_USD_PER_M, GROQ_TEXT_OUTPUT_USD_PER_M,
    GROQ_VISION_INPUT_USD_PER_M, GROQ_VISION_OUTPUT_USD_PER_M,
    GROQ_PROMPT_CACHE_DISCOUNT,
)
from app.models.usage import DailyUsage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CostReservation:
    username: str
    usage_date: date
    amount_usd: float
    enforce_budget: bool = True


def is_creator_account(account) -> bool:
    """Only the flagged canonical father account receives creator exemptions."""
    return bool(account and getattr(account, "is_creator", False)
                and (getattr(account, "username", "") or "").lower() == "father")


def utc_today() -> date:
    return datetime.utcnow().date()


def _get_locked_row(db: Session, username: str) -> DailyUsage:
    normalized = username.lower()
    day = utc_today()
    row = db.query(DailyUsage).filter_by(username=normalized, usage_date=day).first()
    if row is None:
        db.add(DailyUsage(username=normalized, usage_date=day))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # Another request created today's row first.
    row = db.query(DailyUsage).filter_by(username=normalized, usage_date=day).with_for_update().first()
    if row is None:
        raise RuntimeError("Unable to initialize daily usage ledger")
    # Outstanding reservations remain active for the full UTC day unless the
    # provider operation explicitly settles or releases them. We never expire
    # an in-flight reservation by age, because doing so could unlock budget
    # while a slow provider request is still running. Any abandoned reservation
    # expires naturally when the next day's ledger row is used.
    return row


def _limit_error(resource: str, used: float, requested: float, limit: float, unit: str = ""):
    reset = datetime.combine(utc_today() + timedelta(days=1), time.min)
    raise HTTPException(
        status_code=429,
        detail={
            "error": "usage_limit_exceeded",
            "resource": resource,
            "message": f"Daily {resource.replace('_', ' ')} limit reached. Please try again after the daily reset.",
            "used": round(used, 3),
            "requested": round(requested, 3),
            "limit": limit,
            "unit": unit,
            "reset_time": reset.isoformat() + "Z",
        },
    )


def consume_quota(account, db: Session, field: str, amount: float = 1.0) -> float:
    """Atomically consume a bounded daily quota and return the new total."""
    if is_creator_account(account):
        return 0.0
    limits = {
        "text_requests": (FREE_DAILY_TEXT_REQUESTS, "requests"),
        "image_analyses": (FREE_DAILY_IMAGE_ANALYSES, "analyses"),
        "web_searches": (FREE_DAILY_WEB_SEARCHES, "searches"),
        "document_uploads": (FREE_DAILY_DOCUMENT_UPLOADS, "uploads"),
        "transcription_seconds": (FREE_DAILY_TRANSCRIPTION_SECONDS, "seconds"),
        "english_tts_characters": (FREE_DAILY_ENGLISH_TTS_CHARS, "characters"),
    }
    if field not in limits:
        raise ValueError(f"Unknown usage quota: {field}")
    limit, unit = limits[field]
    row = _get_locked_row(db, account.username)
    used = float(getattr(row, field) or 0)
    if used + amount > limit + 1e-9:
        db.rollback()
        _limit_error(field, used, amount, limit, unit)
    new_value = used + amount
    setattr(row, field, int(new_value) if field != "transcription_seconds" else new_value)
    row.updated_at = datetime.utcnow()
    db.commit()
    return new_value


def reserve_ai_budget(account, db: Session, amount_usd: float) -> CostReservation | None:
    """Reserve estimated spend before making a paid provider call."""
    amount = max(0.0, float(amount_usd))
    if is_creator_account(account):
        # Father is never blocked by the free-plan budget, but we still return
        # a reservation marker so actual provider spend is recorded for the
        # creator cost dashboard.
        return CostReservation(account.username.lower(), utc_today(), 0.0, enforce_budget=False)
    row = _get_locked_row(db, account.username)
    committed = float(row.estimated_cost_usd or 0.0)
    reserved = float(row.reserved_cost_usd or 0.0)
    if committed + reserved + amount > FREE_DAILY_AI_BUDGET_USD + 1e-12:
        db.rollback()
        _limit_error("ai_spend_budget_usd", committed + reserved, amount,
                     FREE_DAILY_AI_BUDGET_USD, "USD")
    row.reserved_cost_usd = reserved + amount
    row.updated_at = datetime.utcnow()
    db.commit()
    return CostReservation(account.username.lower(), utc_today(), amount, enforce_budget=True)


def settle_ai_budget(db: Session, reservation: CostReservation | None, actual_cost_usd: float):
    """Release a reservation and record measured/estimated provider cost.

    Creator calls are recorded without a reservation or budget check. This
    keeps cost visibility for Father while preserving his unlimited access.
    """
    if reservation is None:
        return
    row = db.query(DailyUsage).filter_by(
        username=reservation.username, usage_date=reservation.usage_date
    ).with_for_update().first()
    if row is None:
        row = _get_locked_row(db, reservation.username)
    actual = max(0.0, float(actual_cost_usd))
    # Release this request's preflight reservation exactly once when the call
    # settles, then replace it with the measured/estimated actual cost. Keeping
    # completed reservations would double-count every operation and block free
    # users well before their configured $0.05 daily budget.
    if reservation.enforce_budget:
        row.reserved_cost_usd = max(
            0.0,
            float(row.reserved_cost_usd or 0.0) - reservation.amount_usd,
        )
    row.estimated_cost_usd = float(row.estimated_cost_usd or 0.0) + actual
    row.updated_at = datetime.utcnow()
    db.commit()
    if reservation.enforce_budget and row.estimated_cost_usd > FREE_DAILY_AI_BUDGET_USD:
        logger.error("Provider usage exceeded the estimated daily cap for %s: $%.6f",
                     reservation.username, row.estimated_cost_usd)


def add_fixed_cost(account, db: Session, amount_usd: float):
    reservation = reserve_ai_budget(account, db, amount_usd)
    settle_ai_budget(db, reservation, amount_usd if reservation else 0.0)


def _message_content_stats(value) -> tuple[int, int]:
    """Return (text_characters, image_count), deliberately ignoring base64 image data."""
    if isinstance(value, str):
        return len(value), 0
    if isinstance(value, list):
        chars = images = 0
        for item in value:
            item_chars, item_images = _message_content_stats(item)
            chars += item_chars
            images += item_images
        return chars, images
    if isinstance(value, dict):
        chars = images = 0
        for key, item in value.items():
            # Never count data URLs/base64 payloads as text tokens. Estimate image
            # processing separately below; otherwise a 4 MB image can falsely
            # consume the entire daily spend allowance before the provider call.
            if key == "image_url":
                images += 1
                continue
            item_chars, item_images = _message_content_stats(item)
            chars += item_chars
            images += item_images
        if value.get("type") in {"image_url", "input_image"} and not images:
            images = 1
        return chars, images
    return 0, 0


def estimate_input_tokens(messages, vision: bool = False) -> int:
    chars = 0
    image_count = 0
    for message in messages or []:
        content_chars, content_images = _message_content_stats(message.get("content", ""))
        chars += content_chars
        image_count += content_images
    estimated_text_tokens = math.ceil(chars / 2.5)
    if vision and image_count == 0:
        image_count = 1
    # Conservatively model each image as 2,048 input tokens. Base64 bytes are
    # intentionally not included as text tokens.
    return max(1, estimated_text_tokens + image_count * 2048)


def estimate_chat_cost(messages, max_output_tokens: int, vision: bool = False) -> float:
    """Conservative preflight estimate; actual usage is reconciled after response."""
    input_tokens = estimate_input_tokens(messages, vision=vision)
    if vision:
        input_rate, output_rate = GROQ_VISION_INPUT_USD_PER_M, GROQ_VISION_OUTPUT_USD_PER_M
    else:
        input_rate, output_rate = GROQ_TEXT_INPUT_USD_PER_M, GROQ_TEXT_OUTPUT_USD_PER_M
    base = (input_tokens * input_rate + max_output_tokens * output_rate) / 1_000_000
    return max(0.00001, base * 1.5)

def _usage_value(value, key, default=None):
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def extract_usage_metrics(usage) -> dict:
    """Normalize OpenAI-compatible Groq/Cloudflare usage into privacy-safe integers."""
    prompt_tokens = _usage_value(usage, "prompt_tokens")
    completion_tokens = _usage_value(usage, "completion_tokens")
    prompt_details = _usage_value(usage, "prompt_tokens_details")
    completion_details = _usage_value(usage, "completion_tokens_details")
    cached_tokens = _usage_value(prompt_details, "cached_tokens", 0)
    reasoning_tokens = _usage_value(completion_details, "reasoning_tokens", 0)

    def safe_int(raw):
        try:
            return max(0, int(raw or 0))
        except (TypeError, ValueError):
            return 0

    prompt = safe_int(prompt_tokens)
    completion = safe_int(completion_tokens)
    cached = min(prompt, safe_int(cached_tokens))
    reasoning = min(completion, safe_int(reasoning_tokens))
    return {
        "prompt_tokens": prompt,
        "cached_prompt_tokens": cached,
        "completion_tokens": completion,
        "reasoning_tokens": reasoning,
    }


def calculate_chat_cost(
    usage,
    vision: bool = False,
    fallback_input_tokens: int = 0,
    fallback_output_tokens: int = 0,
    cached_input_discount: float | None = None,
) -> float:
    """Calculate cost from reported usage, discounting only confirmed cached text tokens.

    Vision requests do not receive the text prompt-cache discount. If provider
    usage is absent, the estimator is used and no cache discount is assumed.
    """
    metrics = extract_usage_metrics(usage)
    has_reported_usage = usage is not None and (
        _usage_value(usage, "prompt_tokens") is not None
        or _usage_value(usage, "completion_tokens") is not None
    )
    input_tokens = metrics["prompt_tokens"] if has_reported_usage else max(0, int(fallback_input_tokens))
    output_tokens = metrics["completion_tokens"] if has_reported_usage else max(0, int(fallback_output_tokens))
    cached_tokens = metrics["cached_prompt_tokens"] if has_reported_usage and not vision else 0

    input_rate, output_rate = (
        (GROQ_VISION_INPUT_USD_PER_M, GROQ_VISION_OUTPUT_USD_PER_M)
        if vision else (GROQ_TEXT_INPUT_USD_PER_M, GROQ_TEXT_OUTPUT_USD_PER_M)
    )
    discount = GROQ_PROMPT_CACHE_DISCOUNT if cached_input_discount is None else cached_input_discount
    discount = min(1.0, max(0.0, float(discount))) if not vision else 0.0
    uncached_tokens = max(0, input_tokens - cached_tokens)
    billable_input = uncached_tokens + (cached_tokens * (1.0 - discount))
    return (billable_input * input_rate + output_tokens * output_rate) / 1_000_000


def usage_snapshot(account, db: Session) -> dict:
    row = db.query(DailyUsage).filter_by(username=account.username.lower(), usage_date=utc_today()).first()
    if is_creator_account(account):
        # Creator quotas remain unlimited, but actual provider spend is visible.
        return {
            "unlimited": True,
            "estimated_cost_usd": float(row.estimated_cost_usd or 0.0) if row else 0.0,
            "reserved_cost_usd": 0.0,
        }
    values = {
        "text_requests": 0, "image_analyses": 0, "web_searches": 0,
        "document_uploads": 0, "transcription_seconds": 0.0,
        "english_tts_characters": 0, "estimated_cost_usd": 0.0,
        "reserved_cost_usd": 0.0,
    }
    if row:
        for key in values:
            values[key] = getattr(row, key) or 0
    return {
        "unlimited": False,
        **values,
        "limits": {
            "text_requests": FREE_DAILY_TEXT_REQUESTS,
            "image_analyses": FREE_DAILY_IMAGE_ANALYSES,
            "web_searches": FREE_DAILY_WEB_SEARCHES,
            "document_uploads": FREE_DAILY_DOCUMENT_UPLOADS,
            "transcription_seconds": FREE_DAILY_TRANSCRIPTION_SECONDS,
            "english_tts_characters": FREE_DAILY_ENGLISH_TTS_CHARS,
            "ai_spend_usd": FREE_DAILY_AI_BUDGET_USD,
        },
        "ai_budget_remaining_usd": max(0.0, FREE_DAILY_AI_BUDGET_USD - float(values["estimated_cost_usd"]) - float(values["reserved_cost_usd"])),
        "usage_date": utc_today().isoformat(),
    }
