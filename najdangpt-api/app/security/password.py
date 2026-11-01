"""
Password hashing using bcrypt
SECURE: Uses bcrypt with salt, resistant to rainbow tables
"""

import bcrypt

# bcrypt only considers the first 72 bytes of a password. Longer inputs are
# silently truncated, which is surprising and can weaken security reasoning.
# We reject them explicitly instead.
_BCRYPT_MAX_BYTES = 72
MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    """Hash password using bcrypt with auto-generated salt."""
    pw_bytes = password.encode('utf-8')
    if len(pw_bytes) > _BCRYPT_MAX_BYTES:
        raise ValueError("Password too long (max 72 bytes)")
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        pw_bytes = password.encode('utf-8')
        if len(pw_bytes) > _BCRYPT_MAX_BYTES:
            return False
        return bcrypt.checkpw(pw_bytes, password_hash.encode('utf-8'))
    except Exception:
        return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Basic password policy check.
    Returns (ok, message). Use in signup / password-reset flows.
    """
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    if len(password.encode('utf-8')) > _BCRYPT_MAX_BYTES:
        return False, "Password too long (max 72 bytes)"
    return True, "OK"
