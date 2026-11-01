"""
Security utilities
"""

from app.security.validation import validate_username, sanitize_session_id
from app.security.session import (
    generate_session_id, hash_session_token, find_session_by_token,
    migrate_legacy_session_tokens, verify_session_ownership_flexible,
    cleanup_expired_sessions,
)
from app.security.rate_limit import (
    get_client_ip,
    check_account_creation_limit,
    log_account_creation,
    check_message_rate_limit,
    log_message_request,
    check_brute_force_attempts,
    log_failed_login,
    cleanup_old_rate_limit_logs,
)
from app.security.password import hash_password, verify_password
from app.security.dependencies import require_user, require_creator, require_admin

__all__ = [
    "validate_username",
    "sanitize_session_id",
    "generate_session_id",
    "hash_session_token",
    "find_session_by_token",
    "migrate_legacy_session_tokens",
    "verify_session_ownership_flexible",
    "cleanup_expired_sessions",
    "get_client_ip",
    "check_account_creation_limit",
    "log_account_creation",
    "check_message_rate_limit",
    "log_message_request",
    "check_brute_force_attempts",
    "log_failed_login",
    "cleanup_old_rate_limit_logs",
    "hash_password",
    "verify_password",
    "require_user",
    "require_creator",
    "require_admin",
    "usage_snapshot",
    "calculate_chat_cost",
    "estimate_chat_cost",
    "add_fixed_cost",
    "settle_ai_budget",
    "reserve_ai_budget",
    "consume_quota",
    "is_creator_account",
]

from app.security.usage import (
    is_creator_account, consume_quota, reserve_ai_budget, settle_ai_budget,
    add_fixed_cost, estimate_chat_cost, calculate_chat_cost, usage_snapshot,
)
