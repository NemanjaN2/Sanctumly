"""
Input validation and sanitization
"""

import re
from app.config import MIN_USERNAME_LENGTH, MAX_USERNAME_LENGTH


def validate_username(username: str) -> bool:
    """
    Validate username format
    - Alphanumeric, underscore, hyphen only
    - Length between MIN and MAX
    """
    if not username:
        return False
    if len(username) < MIN_USERNAME_LENGTH or len(username) > MAX_USERNAME_LENGTH:
        return False
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False
    return True


def sanitize_session_id(session_id: str) -> str:
    """Sanitize session ID to prevent injection attacks"""
    if not session_id:
        return ""
    return re.sub(r'[^a-zA-Z0-9_-]', '', session_id)
