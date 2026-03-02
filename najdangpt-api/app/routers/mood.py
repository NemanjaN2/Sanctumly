"""
Mood tracking routes - daily check-in and history
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.mood import MoodEntry
from app.models.account import Account

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mood", tags=["Mood"])

EMOJI_MAP = {
    1: "😞",
    2: "😕",
    3: "😐",
    4: "🙂",
    5: "😊"
}

class MoodCheckIn(BaseModel):
    username: str
    session_id: str
    mood_score: int  # 1-5
    note: Optional[str] = None

class MoodResponse(BaseModel):
    success: bool
    message: str
    already_checked_in: bool = False


@router.post("/checkin")
async def mood_checkin(request: MoodCheckIn, db: Session = Depends(get_db)):
    """Submit daily mood check-in"""
    if request.mood_score < 1 or request.mood_score > 5:
        raise HTTPException(status_code=400, detail="Mood score must be 1-5")
    
    # Verify user exists
    user = db.query(Account).filter_by(username=request.username.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already checked in today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    existing = db.query(MoodEntry).filter(
        MoodEntry.username == request.username.lower(),
        MoodEntry.timestamp >= today_start
    ).first()
    
    if existing:
        # Update today's entry instead of creating new
        existing.mood_score = request.mood_score
        existing.emoji = EMOJI_MAP.get(request.mood_score, "😐")
        existing.note = request.note[:500] if request.note else None
        existing.timestamp = datetime.utcnow()
        db.commit()
        return {"success": True, "message": "Mood updated for today", "already_checked_in": True}
    
    # Create new entry
    entry = MoodEntry(
        username=request.username.lower(),
        mood_score=request.mood_score,
        emoji=EMOJI_MAP.get(request.mood_score, "😐"),
        note=request.note[:500] if request.note else None
    )
    db.add(entry)
    db.commit()
    
    logger.info(f"Mood check-in: {request.username} = {request.mood_score}")
    return {"success": True, "message": "Mood recorded", "already_checked_in": False}


@router.get("/history/{username}")
async def mood_history(username: str, days: int = 30, db: Session = Depends(get_db)):
    """Get mood history for a user"""
    if days > 365:
        days = 365
    
    user = db.query(Account).filter_by(username=username.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    since = datetime.utcnow() - timedelta(days=days)
    entries = db.query(MoodEntry).filter(
        MoodEntry.username == username.lower(),
        MoodEntry.timestamp >= since
    ).order_by(MoodEntry.timestamp.asc()).all()
    
    return {
        "username": username,
        "days": days,
        "count": len(entries),
        "entries": [
            {
                "mood_score": e.mood_score,
                "emoji": e.emoji,
                "note": e.note,
                "date": e.timestamp.strftime("%Y-%m-%d"),
                "timestamp": e.timestamp.isoformat()
            }
            for e in entries
        ],
        "average": round(sum(e.mood_score for e in entries) / len(entries), 1) if entries else None
    }


@router.get("/today/{username}")
async def mood_today(username: str, db: Session = Depends(get_db)):
    """Check if user already checked in today"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    existing = db.query(MoodEntry).filter(
        MoodEntry.username == username.lower(),
        MoodEntry.timestamp >= today_start
    ).first()
    
    if existing:
        return {
            "checked_in": True,
            "mood_score": existing.mood_score,
            "emoji": existing.emoji,
            "note": existing.note
        }
    return {"checked_in": False}
