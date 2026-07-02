"""
Speech routes - Speech-to-Text and Text-to-Speech
Uses Groq Whisper for transcription, edge-tts for Serbian TTS, Groq Orpheus for English TTS

SECURITY: Both endpoints require a valid session (they spend your paid Groq
quota) and are counted against the per-user message rate limit. Raw exceptions
are logged server-side but never returned to the client.
"""
import logging
import base64
import tempfile
import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel
from typing import Optional
from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import GROQ_API_KEY
from app.database import get_db
from app.models.account import Account
from app.security import require_user, check_message_rate_limit, log_message_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/speech", tags=["Speech"])

# Groq client for STT and English TTS
groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)

MAX_AUDIO_BYTES = 20 * 1024 * 1024  # 20MB cap on uploaded audio


class TTSRequest(BaseModel):
    text: str
    language: Optional[str] = "en-US"
    voice_gender: Optional[str] = "female"


def _enforce_rate_limit(account: Account, db: Session):
    """Count speech calls against the per-user message limit (creators exempt)."""
    if not check_message_rate_limit(account.username, db):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait.")
    log_message_request(account.username, db)


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    account: Account = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Transcribe audio to text using Groq Whisper (authenticated + rate limited)."""
    _enforce_rate_limit(account, db)
    try:
        audio_content = await file.read()

        if len(audio_content) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio file too large")

        logger.info(f"🎤 Audio from {account.username}: {file.content_type}, {len(audio_content)} bytes")

        if len(audio_content) < 1000:
            return {"success": False, "transcript": "", "error": "Recording too short"}

        suffix = ".m4a"
        if file.filename:
            fn = file.filename.lower()
            if ".webm" in fn: suffix = ".webm"
            elif ".wav" in fn: suffix = ".wav"
            elif ".mp3" in fn: suffix = ".mp3"
            elif ".ogg" in fn or ".opus" in fn: suffix = ".ogg"
            elif ".flac" in fn: suffix = ".flac"

        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(audio_content)
        tmp.close()

        try:
            with open(tmp.name, "rb") as audio_file:
                response = groq_client.audio.transcriptions.create(
                    model="whisper-large-v3-turbo",
                    file=audio_file,
                    response_format="json",
                    temperature=0.0
                )

            transcript = response.text.strip() if hasattr(response, 'text') else ""

            if not transcript:
                return {"success": False, "transcript": "", "error": "No speech detected"}

            logger.info(f"🎤 Transcribed for {account.username}: '{transcript[:50]}...'")
            return {"success": True, "transcript": transcript, "confidence": 0.95}
        finally:
            os.unlink(tmp.name)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Transcription error: {e}")
        # Generic message — don't leak internals to the client
        return {"success": False, "transcript": "", "error": "Transcription failed"}


async def _tts_edge(text: str, language: str) -> bytes:
    """TTS via edge-tts (Croatian voice for Serbian)."""
    import edge_tts

    if language.startswith("sr"):
        voice = "hr-HR-GabrijelaNeural"
    else:
        voice = "en-US-AriaNeural"

    tmp_path = tempfile.mktemp(suffix=".mp3")
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(tmp_path)
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
        logger.info(f"🔊 edge-tts: {len(audio_bytes)} bytes ({voice})")
        return audio_bytes
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def _tts_groq(text: str) -> bytes:
    """TTS via Groq Orpheus (English)."""
    response = groq_client.audio.speech.create(
        model="canopylabs/orpheus-v1-english",
        input=text[:10000],
        voice="autumn",
        response_format="mp3"
    )
    audio_bytes = response.read()
    logger.info(f"🔊 Groq Orpheus: {len(audio_bytes)} bytes")
    return audio_bytes


@router.post("/tts")
async def text_to_speech(
    request: TTSRequest,
    account: Account = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Text to speech (authenticated + rate limited)."""
    _enforce_rate_limit(account, db)
    try:
        text = request.text[:5000] if len(request.text) > 5000 else request.text

        if request.language and request.language.startswith("sr"):
            audio_bytes = await _tts_edge(text, request.language)
            voice_used = "hr-HR-GabrijelaNeural"
            language_code = "sr-RS"
        else:
            try:
                audio_bytes = await _tts_groq(text)
                voice_used = "orpheus-autumn"
                language_code = "en-US"
            except Exception as e:
                logger.warning(f"⚠️ Groq TTS failed, falling back to edge-tts: {e}")
                audio_bytes = await _tts_edge(text, "en-US")
                voice_used = "en-US-AriaNeural"
                language_code = "en-US"

        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        logger.info(f"🔊 TTS for {account.username}: {len(audio_bytes)} bytes ({language_code})")

        return {
            "success": True,
            "audio": audio_base64,
            "format": "mp3",
            "language": language_code,
            "voice": voice_used
        }
    except Exception as e:
        logger.error(f"❌ TTS error: {e}")
        raise HTTPException(status_code=500, detail="TTS failed")


@router.get("/voices")
async def list_voices(_account: Account = Depends(require_user)):
    """List available TTS voices (authenticated)."""
    return {
        "voices": [
            {"code": "en-US", "name": "English (US)", "voice": "autumn (female)", "engine": "Groq Orpheus"},
            {"code": "sr-RS", "name": "Serbian", "voice": "Gabrijela (female)", "engine": "edge-tts"},
        ]
    }
