"""
Authentication routes - Login, Signup
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import LoginRequest, SignupRequest, AuthResponse
from app.models.account import Account, UserSession
from app.security import (
    validate_username,
    hash_password,
    verify_password,
    generate_session_id,
    get_client_ip,
    check_account_creation_limit,
    log_account_creation,
    check_brute_force_attempts,
    log_failed_login,
)
from app.config import MIN_USERNAME_LENGTH, MAX_USERNAME_LENGTH

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, req: Request, db: Session = Depends(get_db)):
    """Authenticate user - NEW LOGINS GET SECURE SESSIONS"""
    client_ip = get_client_ip(req)
    user_agent = req.headers.get("User-Agent", "Unknown")
    
    if not validate_username(request.username):
        log_failed_login(request.username, client_ip, "login", db)
        raise HTTPException(status_code=400, detail="Invalid username format")
    
    if not check_brute_force_attempts(client_ip, db):
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Please try again later."
        )
    
    account = db.query(Account).filter_by(username=request.username.lower()).first()
    
    if not account or not verify_password(request.password, account.password_hash):
        log_failed_login(request.username, client_ip, "login", db)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    account.last_login = datetime.utcnow()
    db.commit()
    
    # Generate secure session ID server-side
    session_id = generate_session_id(account.username)
    
    # Store session in database
    session = UserSession(
        session_id=session_id,
        username=account.username,
        ip_address=client_ip,
        user_agent=user_agent,
        is_secure=True
    )
    db.add(session)
    db.commit()
    
    logger.info(f"✅ Login: {account.username} (creator: {account.is_creator}) from IP: {client_ip}")
    logger.info(f"🔒 Secure session created: {session_id[:30]}...")
    
    return AuthResponse(
        success=True,
        message="Login successful",
        user={
            "username": account.username,
            "is_admin": account.is_admin,
            "is_creator": account.is_creator
        },
        token=session_id,
        session_id=session_id
    )


@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest, req: Request, db: Session = Depends(get_db)):
    """Create new account with rate limiting and input validation"""
    client_ip = get_client_ip(req)
    user_agent = req.headers.get("User-Agent", "Unknown")
    
    if not validate_username(request.username):
        log_failed_login(request.username, client_ip, "signup", db)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid username. Must be {MIN_USERNAME_LENGTH}-{MAX_USERNAME_LENGTH} alphanumeric characters, underscore, or hyphen only."
        )
    
    if not check_account_creation_limit(client_ip, user_agent, db):
        raise HTTPException(
            status_code=429,
            detail="Account creation limit exceeded. Maximum 5 accounts per hour from this device/IP. Please try again later."
        )
    
    if not check_brute_force_attempts(client_ip, db):
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Please try again later."
        )
    
    existing = db.query(Account).filter_by(username=request.username.lower()).first()
    if existing:
        log_failed_login(request.username, client_ip, "signup", db)
        raise HTTPException(status_code=400, detail="Username already exists")
    
    account = Account(
        username=request.username.lower(),
        password_hash=hash_password(request.password),
        email=request.email
    )
    db.add(account)
    db.commit()
    
    log_account_creation(client_ip, user_agent, db)
    
    # Generate secure session for new user
    session_id = generate_session_id(account.username)
    session = UserSession(
        session_id=session_id,
        username=account.username,
        ip_address=client_ip,
        user_agent=user_agent,
        is_secure=True
    )
    db.add(session)
    db.commit()
    
    logger.info(f"✅ Account created: {account.username} from IP: {client_ip}")
    
    return AuthResponse(
        success=True,
        message="Account created successfully",
        user={
            "username": account.username,
            "is_admin": False,
            "is_creator": False
        },
        token=session_id,
        session_id=session_id
    )
