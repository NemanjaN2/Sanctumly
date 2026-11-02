"""Authenticated speech-to-text and text-to-speech with free-tier budgets."""
import asyncio
import base64
import io
import json
import logging
import math
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import (
    GROQ_API_KEY, MAX_AUDIO_BYTES, GROQ_WHISPER_USD_PER_HOUR,
    GROQ_ORPHEUS_USD_PER_M_CHARS,
)
from app.database import get_db
from app.models.account import Account
from app.security import require_user, check_message_rate_limit, log_message_request
from app.security.usage import (
    is_creator_account, consume_quota, reserve_ai_budget, settle_ai_budget,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/speech", tags=["Speech"])
groq_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY, timeout=30.0, max_retries=1)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    language: Optional[str] = "en-US"
    voice_gender: Optional[str] = "female"


def _enforce_hourly_rate_limit(account: Account, db: Session):
    if not check_message_rate_limit(account.username, db):
        raise HTTPException(status_code=429, detail="Speech rate limit exceeded. Please try again later.")
    log_message_request(account.username, db)


def _probe_audio_duration(path: str) -> float | None:
    """Read container duration before making a billable transcription call."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            result = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "json", path],
                capture_output=True, text=True, timeout=8, check=True,
            )
            duration = float(json.loads(result.stdout).get("format", {}).get("duration", 0))
            if math.isfinite(duration) and duration > 0:
                return duration
        except Exception as exc:
            logger.warning("ffprobe duration detection failed: %s", type(exc).__name__)
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(path)
        duration = float(audio.info.length) if audio and audio.info else 0.0
        if math.isfinite(duration) and duration > 0:
            return duration
    except Exception:
        pass
    try:
        with wave.open(path, "rb") as wav_file:
            duration = wav_file.getnframes() / float(wav_file.getframerate())
            return duration if duration > 0 else None
    except Exception:
        return None


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    account: Account = Depends(require_user),
    db: Session = Depends(get_db),
):
    _enforce_hourly_rate_limit(account, db)
    content = await file.read(MAX_AUDIO_BYTES + 1)
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large")
    if len(content) < 1000:
        return {"success": False, "transcript": "", "error": "Recording too short"}

    suffix = Path(file.filename or "recording.m4a").suffix.lower()
    if suffix not in {".m4a", ".mp4", ".webm", ".wav", ".mp3", ".ogg", ".opus", ".flac", ".mpeg", ".mpga"}:
        suffix = ".m4a"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            temp_path = tmp.name
        duration = _probe_audio_duration(temp_path)
        creator = is_creator_account(account)
        reservation = None
        if duration is None and not creator:
            raise HTTPException(status_code=400, detail="Could not verify recording duration. Please record again using a supported audio format.")
        seconds = math.ceil(duration * 10) / 10 if duration is not None else 0.0
        if not creator and seconds > 300:
            raise HTTPException(status_code=413, detail="A free-plan recording cannot exceed 5 minutes")
        reservation_amount = (seconds / 3600.0) * GROQ_WHISPER_USD_PER_HOUR * 1.20
        reservation = reserve_ai_budget(account, db, reservation_amount)
        if not creator:
            try:
                consume_quota(account, db, "transcription_seconds", seconds)
            except Exception:
                settle_ai_budget(db, reservation, 0.0)
                raise

        try:
            def _transcribe():
                with open(temp_path, "rb") as audio_file:
                    return groq_client.audio.transcriptions.create(
                        model="whisper-large-v3-turbo",
                        file=audio_file,
                        response_format="json",
                        temperature=0.0,
                    )
            response = await asyncio.to_thread(_transcribe)
            transcript = response.text.strip() if hasattr(response, "text") else ""
            if reservation is not None:
                measured_seconds = duration if duration is not None else 0.0
                actual_cost = (measured_seconds / 3600.0) * GROQ_WHISPER_USD_PER_HOUR
                settle_ai_budget(db, reservation, actual_cost)
                reservation = None
            if not transcript:
                return {"success": False, "transcript": "", "error": "No speech detected"}
            return {"success": True, "transcript": transcript, "confidence": 0.95}
        except Exception:
            if reservation is not None:
                settle_ai_budget(db, reservation, 0.0)
            raise
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Transcription failed for %s", account.username)
        return {"success": False, "transcript": "", "error": "Transcription failed"}
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


async def _tts_edge(text: str, language: str) -> bytes:
    import edge_tts
    voice = "hr-HR-GabrijelaNeural" if language.startswith("sr") else "en-US-AriaNeural"
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        await edge_tts.Communicate(text, voice).save(tmp_path)
        with open(tmp_path, "rb") as audio_file:
            return audio_file.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _split_tts_text(text: str, max_chars: int = 200) -> list[str]:
    remaining = text.strip()
    chunks = []
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        split_at = remaining.rfind(" ", 0, max_chars + 1)
        if split_at < max_chars // 2:
            split_at = max_chars
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    return [chunk for chunk in chunks if chunk]


def _merge_wav_chunks(parts: list[bytes]) -> bytes:
    frames = []
    params = None
    for item in parts:
        with wave.open(io.BytesIO(item), "rb") as reader:
            current_params = reader.getparams()
            current_frames = reader.readframes(reader.getnframes())
        comparable = (current_params.nchannels, current_params.sampwidth,
                      current_params.framerate, current_params.comptype)
        if params is None:
            params = (comparable, current_params)
        elif params[0] != comparable:
            raise ValueError("TTS audio chunks have incompatible formats")
        frames.append(current_frames)
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setparams(params[1])
        writer.writeframes(b"".join(frames))
    return output.getvalue()


def _wav_to_mp3(wav_bytes: bytes) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is not installed")
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-f", "mp3", "-codec:a", "libmp3lame", "-q:a", "4", "pipe:1"],
        input=wav_bytes, capture_output=True, timeout=30, check=True,
    )
    if not result.stdout:
        raise RuntimeError("Audio conversion returned no data")
    return result.stdout


def _tts_groq_mp3(text: str, successful_characters: list[int] | None = None) -> bytes:
    """Orpheus accepts at most 200 chars and WAV; preserve client MP3 contract.

    successful_characters is a mutable one-item counter used by the caller to
    account for chunks that completed before a later chunk/conversion failed.
    """
    wav_parts = []
    for chunk in _split_tts_text(text, 200):
        response = groq_client.audio.speech.create(
            model="canopylabs/orpheus-v1-english",
            input=chunk,
            voice="autumn",
            response_format="wav",
        )
        wav_parts.append(response.read())
        if successful_characters is not None:
            successful_characters[0] += len(chunk)
    merged = _merge_wav_chunks(wav_parts)
    return _wav_to_mp3(merged)


@router.post("/tts")
async def text_to_speech(
    request: TTSRequest,
    account: Account = Depends(require_user),
    db: Session = Depends(get_db),
):
    _enforce_hourly_rate_limit(account, db)
    creator = is_creator_account(account)
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text must not be empty")
    is_serbian = bool(request.language and request.language.lower().startswith("sr"))

    reservation = None
    if not is_serbian:
        reserve_amount = len(text) * GROQ_ORPHEUS_USD_PER_M_CHARS / 1_000_000 * 1.20
        reservation = reserve_ai_budget(account, db, reserve_amount)
        if not creator:
            try:
                consume_quota(account, db, "english_tts_characters", len(text))
            except Exception:
                settle_ai_budget(db, reservation, 0.0)
                reservation = None
                raise

    groq_tts_successful_characters = [0]
    try:
        if is_serbian:
            audio_bytes = await _tts_edge(text, request.language or "sr-RS")
            voice_used, language_code = "hr-HR-GabrijelaNeural", "sr-RS"
        else:
            try:
                audio_bytes = await asyncio.to_thread(_tts_groq_mp3, text, groq_tts_successful_characters)
                voice_used, language_code = "orpheus-autumn", "en-US"
            except Exception as exc:
                logger.warning("Groq TTS failed; using Edge TTS fallback: %s", type(exc).__name__)
                audio_bytes = await _tts_edge(text, "en-US")
                voice_used, language_code = "en-US-AriaNeural", "en-US"

        if reservation is not None:
            # Edge TTS fallback is not a Groq-billed operation. Keep the daily
            # character quota (abuse control), but do not charge estimated Groq
            # spend when the fallback actually produced the audio.
            measured_cost = (groq_tts_successful_characters[0]
                             * GROQ_ORPHEUS_USD_PER_M_CHARS / 1_000_000)
            settle_ai_budget(db, reservation, measured_cost)
            reservation = None
        return {
            "success": True,
            "audio": base64.b64encode(audio_bytes).decode("utf-8"),
            "format": "mp3",
            "language": language_code,
            "voice": voice_used,
        }
    except Exception:
        if reservation is not None:
            settle_ai_budget(db, reservation, 0.0)
        logger.exception("TTS failed for %s", account.username)
        raise HTTPException(status_code=502, detail="TTS failed")


@router.get("/voices")
async def list_voices(_account: Account = Depends(require_user)):
    return {"voices": [
        {"code": "en-US", "name": "English (US)", "voice": "autumn (female)", "engine": "Groq Orpheus"},
        {"code": "sr-RS", "name": "Serbian", "voice": "Gabrijela (female)", "engine": "edge-tts"},
    ]}
