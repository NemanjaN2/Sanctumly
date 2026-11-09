"""
Authentication schemas
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any


class LoginRequest(BaseModel):
    username: str
    password: str


class SignupRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


class AuthResponse(BaseModel):
    success: bool
    message: str
    user: Optional[Dict[str, Any]] = None
    token: Optional[str] = None
    session_id: Optional[str] = None
