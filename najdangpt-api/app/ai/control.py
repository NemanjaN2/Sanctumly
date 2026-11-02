"""Database-backed, expiring manual model routing controls."""
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.rate_limit import Settings

SETTING_KEY = "ai_provider_override"


def get_provider_override(db: Session) -> dict:
    setting = db.query(Settings).filter_by(key=SETTING_KEY).first()
    if not setting or not setting.value:
        return {"mode": "auto", "active": False, "expires_at": None}
    try:
        data = json.loads(setting.value)
    except (TypeError, ValueError):
        return {"mode": "auto", "active": False, "expires_at": None}

    mode = data.get("mode", "auto")
    if mode != "groq":
        return {"mode": "auto", "active": False, "expires_at": None}

    expires_raw = data.get("expires_at")
    try:
        expires_at = datetime.fromisoformat(str(expires_raw).replace("Z", "+00:00"))
        if expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError):
        return {"mode": "auto", "active": False, "expires_at": None}

    now = datetime.utcnow()
    active = expires_at > now
    return {
        "mode": "groq" if active else "auto",
        "active": active,
        "expires_at": expires_at.isoformat() + "Z" if active else None,
        "updated_at": data.get("updated_at"),
        "updated_by": data.get("updated_by"),
    }


def set_provider_override(db: Session, mode: str, duration_minutes: int = 60, updated_by: str = "father") -> dict:
    mode = (mode or "").lower().strip()
    if mode not in {"auto", "groq"}:
        raise ValueError("mode must be 'auto' or 'groq'")

    now = datetime.utcnow()
    if mode == "auto":
        payload = {
            "mode": "auto",
            "expires_at": None,
            "updated_at": now.isoformat() + "Z",
            "updated_by": updated_by,
        }
    else:
        duration_minutes = max(15, min(int(duration_minutes), 1440))
        expires_at = now + timedelta(minutes=duration_minutes)
        payload = {
            "mode": "groq",
            "expires_at": expires_at.isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
            "updated_by": updated_by,
        }

    setting = db.query(Settings).filter_by(key=SETTING_KEY).first()
    if setting:
        setting.value = json.dumps(payload, separators=(",", ":"))
        setting.updated_at = now
    else:
        db.add(Settings(key=SETTING_KEY, value=json.dumps(payload, separators=(",", ":"))))
    db.commit()
    return get_provider_override(db)
