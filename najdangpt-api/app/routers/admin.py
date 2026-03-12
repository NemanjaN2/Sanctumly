"""
Admin routes - Settings, security monitoring, rate limits, therapist knowledge base
"""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.account import Account, UserSession, FailedLoginAttempt
from app.models.rate_limit import Settings, MessageRateLimit
from app.models.therapist_knowledge import TherapistKnowledge
from app.security import validate_username, cleanup_old_rate_limit_logs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


# ===== Therapist Knowledge Schemas =====

class TherapistKnowledgeCreate(BaseModel):
    category: str
    title: str
    content: str
    author: Optional[str] = None

class TherapistKnowledgeUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    is_active: Optional[bool] = None


# ===== Settings =====

@router.get("/settings")
async def get_settings(db: Session = Depends(get_db)):
    """Get all settings"""
    settings = db.query(Settings).all()
    return {setting.key: setting.value for setting in settings}


@router.post("/settings")
async def save_setting(key: str, value: str, db: Session = Depends(get_db)):
    """Save a setting"""
    setting = db.query(Settings).filter_by(key=key).first()
    
    if setting:
        setting.value = value
        setting.updated_at = datetime.utcnow()
    else:
        setting = Settings(key=key, value=value)
        db.add(setting)
    
    db.commit()
    return {"success": True, "key": key}


@router.post("/cleanup-rate-limits")
async def manual_cleanup(db: Session = Depends(get_db)):
    """Manually trigger rate limit log cleanup"""
    try:
        cleanup_old_rate_limit_logs(db)
        return {"success": True, "message": "Cleanup completed"}
    except Exception as e:
        logger.error(f"❌ Manual cleanup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Security Monitoring =====

@router.get("/security/failed-logins")
async def get_failed_login_stats(db: Session = Depends(get_db)):
    """Get failed login attempt statistics for security monitoring"""
    try:
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        
        failed_last_hour = db.query(FailedLoginAttempt).filter(
            FailedLoginAttempt.timestamp >= one_hour_ago
        ).count()
        
        failed_last_day = db.query(FailedLoginAttempt).filter(
            FailedLoginAttempt.timestamp >= twenty_four_hours_ago
        ).count()
        
        top_ips = db.query(
            FailedLoginAttempt.ip_address,
            func.count(FailedLoginAttempt.id).label('count')
        ).filter(
            FailedLoginAttempt.timestamp >= twenty_four_hours_ago
        ).group_by(
            FailedLoginAttempt.ip_address
        ).order_by(
            func.count(FailedLoginAttempt.id).desc()
        ).limit(10).all()
        
        return {
            "failed_logins_last_hour": failed_last_hour,
            "failed_logins_last_24h": failed_last_day,
            "top_offending_ips": [
                {"ip": ip, "attempts": count} for ip, count in top_ips
            ]
        }
    except Exception as e:
        logger.error(f"❌ Failed login stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/security/sessions")
async def get_session_stats(db: Session = Depends(get_db)):
    """Get session security statistics"""
    try:
        total_sessions = db.query(UserSession).count()
        secure_sessions = db.query(UserSession).filter_by(is_secure=True).count()
        
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        active_last_hour = db.query(UserSession).filter(
            UserSession.last_used >= one_hour_ago
        ).count()
        
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        active_last_day = db.query(UserSession).filter(
            UserSession.last_used >= twenty_four_hours_ago
        ).count()
        
        return {
            "total_sessions": total_sessions,
            "secure_sessions": secure_sessions,
            "legacy_sessions": total_sessions - secure_sessions,
            "active_last_hour": active_last_hour,
            "active_last_24h": active_last_day
        }
    except Exception as e:
        logger.error(f"❌ Session stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rate-limit/status/{username}")
async def get_rate_limit_status(username: str, db: Session = Depends(get_db)):
    """Get current rate limit status for a user - no enumeration"""
    try:
        if not validate_username(username):
            raise HTTPException(status_code=400, detail="Invalid username")
        
        account = db.query(Account).filter_by(username=username.lower()).first()
        is_creator = account.is_creator if account else False
        
        if is_creator:
            return {
                "username": username,
                "unlimited": True,
                "message_count": 0,
                "messages_remaining": "unlimited",
                "reset_time": None
            }
        
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        message_count = db.query(MessageRateLimit).filter(
            MessageRateLimit.username == username.lower(),
            MessageRateLimit.timestamp >= one_hour_ago
        ).count()
        
        messages_remaining = max(0, 30 - message_count)
        
        oldest_message = db.query(MessageRateLimit).filter(
            MessageRateLimit.username == username.lower(),
            MessageRateLimit.timestamp >= one_hour_ago
        ).order_by(MessageRateLimit.timestamp.asc()).first()
        
        reset_time = None
        if oldest_message:
            reset_time = (oldest_message.timestamp + timedelta(hours=1)).isoformat()
        
        return {
            "username": username,
            "unlimited": False,
            "message_count": message_count,
            "messages_remaining": messages_remaining,
            "reset_time": reset_time
        }
    except Exception as e:
        logger.error(f"❌ Rate limit status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Password Reset (Creator Only) =====

from app.security import hash_password as secure_hash

@router.post("/reset-password")
async def admin_reset_password(request: dict, db: Session = Depends(get_db)):
    """Creator-only: Reset any non-creator user's password"""
    admin_username = request.get("admin_username", "")
    target_username = request.get("target_username", "")
    new_password = request.get("new_password", "")
    
    if not all([admin_username, target_username, new_password]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    admin = db.query(Account).filter_by(username=admin_username.lower()).first()
    if not admin or not admin.is_creator:
        raise HTTPException(status_code=403, detail="Only creator can reset passwords")
    
    target = db.query(Account).filter_by(username=target_username.lower()).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    if target.is_creator:
        raise HTTPException(status_code=403, detail="Cannot reset creator account password")
    
    target.password_hash = secure_hash(new_password)
    db.commit()
    
    logger.info(f"Password reset by {admin_username} for user: {target_username}")
    
    return {"success": True, "message": f"Password reset for {target_username}"}


# ===== View User Messages (Creator Only) =====

from app.models.chat import Message

@router.get("/messages")
async def get_user_messages(
    admin_username: str,
    limit: int = 50,
    username: str = None,
    db: Session = Depends(get_db)
):
    """Creator-only: View user messages"""
    admin = db.query(Account).filter_by(username=admin_username.lower()).first()
    if not admin or not admin.is_creator:
        raise HTTPException(status_code=403, detail="Only creator can view messages")
    
    query = db.query(Message).order_by(Message.timestamp.desc())
    
    if username:
        query = query.filter(Message.username == username.lower())
    
    messages = query.limit(min(limit, 200)).all()
    
    return {
        "count": len(messages),
        "messages": [
            {
                "id": m.id,
                "username": m.username,
                "role": m.role,
                "content": m.content[:500],
                "timestamp": m.timestamp.isoformat() if m.timestamp else None
            }
            for m in messages
        ]
    }


# ===== Therapist Knowledge Base =====

@router.get("/therapist-knowledge/categories/list")
async def list_categories(db: Session = Depends(get_db)):
    """Get all unique categories"""
    categories = db.query(TherapistKnowledge.category).distinct().all()
    return {"categories": [c[0] for c in categories]}


@router.get("/therapist-knowledge")
async def list_therapist_knowledge(db: Session = Depends(get_db)):
    """List all therapist knowledge entries"""
    entries = db.query(TherapistKnowledge).order_by(
        TherapistKnowledge.category,
        TherapistKnowledge.created_at.desc()
    ).all()
    
    return {
        "entries": [
            {
                "id": e.id,
                "category": e.category,
                "title": e.title,
                "content": e.content,
                "author": e.author,
                "is_active": e.is_active,
                "created_at": e.created_at.isoformat(),
                "updated_at": e.updated_at.isoformat()
            }
            for e in entries
        ]
    }


@router.get("/therapist-knowledge/{entry_id}")
async def get_therapist_knowledge(entry_id: int, db: Session = Depends(get_db)):
    """Get a single knowledge entry"""
    entry = db.query(TherapistKnowledge).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return {
        "id": entry.id,
        "category": entry.category,
        "title": entry.title,
        "content": entry.content,
        "author": entry.author,
        "is_active": entry.is_active,
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat()
    }


@router.post("/therapist-knowledge")
async def create_therapist_knowledge(data: TherapistKnowledgeCreate, db: Session = Depends(get_db)):
    """Add a new therapist knowledge entry"""
    entry = TherapistKnowledge(
        category=data.category.strip(),
        title=data.title.strip(),
        content=data.content.strip(),
        author=data.author.strip() if data.author else None
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    
    logger.info(f"Therapist knowledge added: '{entry.title}' [{entry.category}]")
    
    return {
        "success": True,
        "id": entry.id,
        "message": f"Added: {entry.title}"
    }


@router.put("/therapist-knowledge/{entry_id}")
async def update_therapist_knowledge(entry_id: int, data: TherapistKnowledgeUpdate, db: Session = Depends(get_db)):
    """Update an existing knowledge entry"""
    entry = db.query(TherapistKnowledge).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    if data.category is not None:
        entry.category = data.category.strip()
    if data.title is not None:
        entry.title = data.title.strip()
    if data.content is not None:
        entry.content = data.content.strip()
    if data.author is not None:
        entry.author = data.author.strip() if data.author else None
    if data.is_active is not None:
        entry.is_active = data.is_active
    
    entry.updated_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"Therapist knowledge updated: '{entry.title}' [active={entry.is_active}]")
    
    return {"success": True, "message": f"Updated: {entry.title}"}


@router.delete("/therapist-knowledge/{entry_id}")
async def delete_therapist_knowledge(entry_id: int, db: Session = Depends(get_db)):
    """Delete a knowledge entry"""
    entry = db.query(TherapistKnowledge).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    title = entry.title
    db.delete(entry)
    db.commit()
    
    logger.info(f"🗑️ Therapist knowledge deleted: '{title}'")
    
    return {"success": True, "message": f"Deleted: {title}"}
