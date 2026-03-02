"""
Password hashing using bcrypt
SECURE: Uses bcrypt with salt, resistant to rainbow tables
"""

import bcrypt


def hash_password(password: str) -> str:
    """Hash password using bcrypt with auto-generated salt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against bcrypt hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False
