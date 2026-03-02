"""
Rate limiting and brute force protection
"""

import logging
from datetime import datetime, timedelta
from fastapi import Request
from sqlalchemy.orm import Session
from app.config import MAX_ACCOUNTS_PER_HOUR, MAX_MESSAGES_PER_HOUR, MAX_FAILED_LOGINS_PER_HOUR
from app.models.account import Account, FailedLoginAttempt
from app.models.rate_limit import MessageRateLimit, AccountCreationLog

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxies"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    if request.client:
        return request.client.host
    
    return "unknown"


def check_account_creation_limit(ip_address: str, user_agent: str, db: Session) -> bool:
    """Check if IP has exceeded account creation limit"""
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    count = db.query(AccountCreationLog).filter(
        AccountCreationLog.ip_address == ip_address,
        AccountCreationLog.created_at >= one_hour_ago
    ).count()
    
    if count >= MAX_ACCOUNTS_PER_HOUR:
        logger.warning(f"🚫 Rate limit: IP {ip_address} exceeded account creation limit ({count}/{MAX_ACCOUNTS_PER_HOUR})")
        return False
    
    return True


def log_account_creation(ip_address: str, user_agent: str, db: Session):
    """Log account creation for rate limiting"""
    log_entry = AccountCreationLog(
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(log_entry)
    db.commit()
    logger.info(f"✅ Logged account creation from IP: {ip_address}")


def check_message_rate_limit(username: str, db: Session) -> bool:
    """Check if user has exceeded message limit"""
    # Creator bypass
    account = db.query(Account).filter_by(username=username.lower()).first()
    if account and account.is_creator:
        logger.info(f"👑 Creator Mode: {username} - Rate limit bypassed")
        return True
    
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    count = db.query(MessageRateLimit).filter(
        MessageRateLimit.username == username.lower(),
        MessageRateLimit.timestamp >= one_hour_ago
    ).count()
    
    if count >= MAX_MESSAGES_PER_HOUR:
        logger.warning(f"🚫 Rate limit: User {username} exceeded message limit ({count}/{MAX_MESSAGES_PER_HOUR})")
        return False
    
    return True


def log_message_request(username: str, db: Session):
    """Log message request for rate limiting"""
    log_entry = MessageRateLimit(username=username.lower())
    db.add(log_entry)
    db.commit()


def check_brute_force_attempts(ip_address: str, db: Session) -> bool:
    """Check if IP has excessive failed login attempts"""
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    attempt_count = db.query(FailedLoginAttempt).filter(
        FailedLoginAttempt.ip_address == ip_address,
        FailedLoginAttempt.timestamp >= one_hour_ago
    ).count()
    
    if attempt_count >= MAX_FAILED_LOGINS_PER_HOUR:
        logger.warning(f"🚨 BRUTE FORCE DETECTED: IP {ip_address} has {attempt_count} failed attempts")
        return False
    
    return True


def log_failed_login(username: str, ip_address: str, attempt_type: str, db: Session):
    """Log failed login/signup attempts for security monitoring"""
    try:
        attempt = FailedLoginAttempt(
            username=username.lower() if username else "unknown",
            ip_address=ip_address,
            attempt_type=attempt_type
        )
        db.add(attempt)
        db.commit()
        logger.warning(f"🚨 Failed {attempt_type} attempt: {username} from IP: {ip_address}")
    except Exception as e:
        logger.error(f"❌ Failed to log failed attempt: {e}")
        db.rollback()


def cleanup_old_rate_limit_logs(db: Session):
    """Clean up rate limit logs older than 24 hours"""
    try:
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        
        deleted_accounts = db.query(AccountCreationLog).filter(
            AccountCreationLog.created_at < twenty_four_hours_ago
        ).delete()
        
        deleted_messages = db.query(MessageRateLimit).filter(
            MessageRateLimit.timestamp < twenty_four_hours_ago
        ).delete()
        
        deleted_failed_logins = db.query(FailedLoginAttempt).filter(
            FailedLoginAttempt.timestamp < twenty_four_hours_ago
        ).delete()
        
        db.commit()
        
        if deleted_accounts > 0 or deleted_messages > 0 or deleted_failed_logins > 0:
            logger.info(f"🧹 Cleanup: Removed {deleted_accounts} account logs, {deleted_messages} message logs, {deleted_failed_logins} failed login logs")
    except Exception as e:
        logger.error(f"❌ Cleanup error: {e}")
        db.rollback()
