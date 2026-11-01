"""Authenticated feedback routes."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.chat import MessageFeedback, Message
from app.models.account import Account
from app.security import require_user, require_creator, validate_username, sanitize_session_id
from app.security.usage import is_creator_account

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feedback", tags=["Feedback"])

class FeedbackSubmission(BaseModel):
    session_id: str
    message_content: str = ""
    feedback_type: str
    username: str = ""



@router.post("/submit")
async def submit_feedback(
    session_id: str | None = None,
    message_content: str = "",
    feedback_type: str | None = None,
    username: str = "",
    payload: FeedbackSubmission | None = Body(default=None),
    account: Account = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Record feedback; accept both legacy query fields and JSON clients."""
    if payload is not None:
        session_id = payload.session_id
        message_content = payload.message_content
        feedback_type = payload.feedback_type
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if feedback_type not in {"like", "dislike"}:
        raise HTTPException(status_code=400, detail="feedback_type must be 'like' or 'dislike'")
    clean_session_id = sanitize_session_id(session_id)
    if not clean_session_id:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    owns = db.query(Message).filter_by(
        session_id=clean_session_id, username=account.username.lower()
    ).first()
    if not owns and not is_creator_account(account):
        raise HTTPException(status_code=403, detail="Conversation does not belong to this account")
    feedback = MessageFeedback(
        session_id=clean_session_id,
        username=account.username.lower(),
        message_content=(message_content or "")[:12000],
        feedback_type=feedback_type,
    )
    db.add(feedback)
    db.commit()
    return {"success": True, "message": "Feedback recorded"}


@router.get("/stats")
async def get_feedback_stats(_creator: Account = Depends(require_creator), db: Session = Depends(get_db)):
    total = db.query(MessageFeedback).count()
    likes = db.query(MessageFeedback).filter_by(feedback_type="like").count()
    dislikes = db.query(MessageFeedback).filter_by(feedback_type="dislike").count()
    return {"total": total, "likes": likes, "dislikes": dislikes,
            "like_percentage": round((likes / total * 100) if total else 0, 2)}


@router.get("/user/{username}")
async def get_user_feedback(
    username: str,
    account: Account = Depends(require_user),
    db: Session = Depends(get_db),
):
    if not validate_username(username):
        raise HTTPException(status_code=400, detail="Invalid username")
    if not is_creator_account(account) and account.username.lower() != username.lower():
        raise HTTPException(status_code=403, detail="Forbidden")
    feedbacks = db.query(MessageFeedback).filter_by(username=username.lower())\
        .order_by(MessageFeedback.timestamp.desc()).limit(50).all()
    return {"username": username, "feedbacks": [
        {"feedback_type": f.feedback_type, "timestamp": f.timestamp.isoformat(),
         "message_preview": (f.message_content or "")[:100] + ("..." if len(f.message_content or "") > 100 else "")}
        for f in feedbacks
    ]}
