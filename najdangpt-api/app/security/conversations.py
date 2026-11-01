"""Authorization helpers for per-chat conversation identifiers."""
import logging
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.account import UserSession
from app.models.chat import Message
from app.models.document import UserDocument
from app.models.conversation import ConversationSession
from app.security.validation import sanitize_session_id
from app.security.session import find_session_by_token
from app.security.usage import is_creator_account

logger = logging.getLogger(__name__)


def authorize_conversation_session(session_id: str, account, db: Session) -> str:
    """Bind a chat context ID to the authenticated owner, preserving legacy IDs.

    iOS/Android currently send the login session ID as their chat ID. The web
    client uses a distinct local chat ID and authenticates with Authorization.
    Both forms are supported. A conversation ID can never be claimed by a
    different non-creator account.
    """
    raw_id = (session_id or "").strip()
    clean_id = sanitize_session_id(raw_id)
    if not clean_id or clean_id != raw_id or len(clean_id) > 100:
        raise HTTPException(status_code=400, detail="A valid session_id is required")

    username = (account.username or "").lower()
    creator = is_creator_account(account)
    existing = db.query(ConversationSession).filter_by(session_id=clean_id).first()
    if existing:
        if existing.username.lower() != username and not creator:
            raise HTTPException(status_code=403, detail="Conversation does not belong to this account")
        existing.last_used = datetime.utcnow()
        db.commit()
        return clean_id

    # Backfill legacy login-session conversations and historical messages.
    legacy_auth = find_session_by_token(clean_id, db)
    if legacy_auth and legacy_auth.username.lower() != username and not creator:
        raise HTTPException(status_code=403, detail="Session does not belong to this account")

    owners = [row[0].lower() for row in db.query(Message.username).filter_by(
        session_id=clean_id
    ).distinct().all() if row and row[0]]
    has_legacy_documents = db.query(UserDocument.id).filter_by(session_id=clean_id).first() is not None
    if has_legacy_documents and not owners and not legacy_auth and not creator:
        # Older document rows have no username column. If there is no legacy
        # auth session or message owner to prove who uploaded them, do not let
        # an arbitrary account claim the ID and retrieve potentially private
        # document context. Creator can still administer/recover this data.
        raise HTTPException(
            status_code=403,
            detail="This conversation has legacy documents with unknown ownership. Start a new conversation and upload them again.",
        )
    if owners and not creator and set(owners) != {username}:
        # Legacy tables had no conversation ownership table. Refuse ambiguous
        # mixed-owner IDs instead of allowing one participant to read another
        # account's messages through a historically shared context identifier.
        raise HTTPException(status_code=403, detail="Conversation ownership is ambiguous")

    # A creator inspecting another user's historical conversation must not
    # reassign its ownership to father.
    owner = (legacy_auth.username.lower() if legacy_auth else (owners[0] if owners else username))
    row = ConversationSession(
        session_id=clean_id,
        username=owner,
        created_at=datetime.utcnow(),
        last_used=datetime.utcnow(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(ConversationSession).filter_by(session_id=clean_id).first()
        if not existing or (existing.username.lower() != username and not creator):
            raise HTTPException(status_code=403, detail="Conversation does not belong to this account")
    return clean_id
