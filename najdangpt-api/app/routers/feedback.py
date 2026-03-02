"""
User feedback routes
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chat import MessageFeedback
from app.security import validate_username

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("/submit")
async def submit_feedback(
    session_id: str,
    message_content: str,
    feedback_type: str,
    username: str = "",
    db: Session = Depends(get_db)
):
    """Store user feedback on AI responses"""
    try:
        feedback = MessageFeedback(
            session_id=session_id,
            username=username.lower(),
            message_content=message_content,
            feedback_type=feedback_type
        )
        db.add(feedback)
        db.commit()
        
        logger.info(f"📊 Feedback: {username} gave '{feedback_type}'")
        
        return {"success": True, "message": "Feedback recorded"}
    except Exception as e:
        logger.error(f"❌ Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_feedback_stats(db: Session = Depends(get_db)):
    """Get feedback statistics"""
    try:
        total = db.query(MessageFeedback).count()
        likes = db.query(MessageFeedback).filter_by(feedback_type='like').count()
        dislikes = db.query(MessageFeedback).filter_by(feedback_type='dislike').count()
        
        return {
            "total": total,
            "likes": likes,
            "dislikes": dislikes,
            "like_percentage": round((likes / total * 100) if total > 0 else 0, 2)
        }
    except Exception as e:
        logger.error(f"❌ Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{username}")
async def get_user_feedback(username: str, db: Session = Depends(get_db)):
    """Get feedback for specific user"""
    try:
        if not validate_username(username):
            raise HTTPException(status_code=400, detail="Invalid username")
        
        feedbacks = db.query(MessageFeedback)\
            .filter_by(username=username.lower())\
            .order_by(MessageFeedback.timestamp.desc())\
            .limit(50)\
            .all()
        
        return {
            "username": username,
            "feedbacks": [
                {
                    "feedback_type": f.feedback_type,
                    "timestamp": f.timestamp.isoformat(),
                    "message_preview": f.message_content[:100] + "..." if len(f.message_content) > 100 else f.message_content
                }
                for f in feedbacks
            ]
        }
    except Exception as e:
        logger.error(f"❌ User feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
