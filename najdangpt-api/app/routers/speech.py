"""
Speech routes - Speech-to-Text and Text-to-Speech
Uses Groq Whisper for transcription, edge-tts for Serbian TTS, Groq Orpheus for English TTS
"""
import logging
import base64
import io
import tempfile
import os
import asyncio
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from openai import OpenAI
from app.config import GROQ_API_KEY

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/speech", tags=["Speech"])

# Groq client for STT and English TTS
groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)


class TTSRequest(BaseModel):
    text: str
    language: Optional[str] = "en-US"
    voice_gender: Optional[str] = "female"


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe audio to text using Groq Whisper"""
    try:
        audio_content = await file.read()

        logger.info(f"🎤 Received audio: {file.filename}, type: {file.content_type}, size: {len(audio_content)} bytes")

        # Check minimum size
        if len(audio_content) < 1000:
            logger.warning(f"⚠️ Audio too small: {len(audio_content)} bytes")
            return {
                "success": False,
                "transcript": "",
                "error": "Recording too short"
            }

        # Write to temp file (Groq needs a file object with a name)
        suffix = ".m4a"
        if file.filename:
            fn = file.filename.lower()
            if ".webm" in fn:
                suffix = ".webm"
            elif ".wav" in fn:
                suffix = ".wav"
            elif ".mp3" in fn:
                suffix = ".mp3"
            elif ".ogg" in fn or ".opus" in fn:
                suffix = ".ogg"
            elif ".flac" in fn:
                suffix = ".flac"

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
                logger.warning("⚠️ No speech detected in audio")
                return {
                    "success": False,
                    "transcript": "",
                    "error": "No speech detected"
                }

            logger.info(f"🎤 Transcribed: '{transcript[:50]}...'")

            return {
                "success": True,
                "transcript": transcript,
                "confidence": 0.95
            }

        finally:
            os.unlink(tmp.name)

    except Exception as e:
        logger.error(f"❌ Transcription error: {e}")
        return {
            "success": False,
            "transcript": "",
            "error": str(e)
        }


async def _tts_edge(text: str, language: str) -> bytes:
    """Generate TTS audio using edge-tts for Serbian (Croatian voice for better pronunciation)"""
    import edge_tts

    if language.startswith("sr"):
        # Croatian female - same language family, much better Serbian pronunciation than SophieNeural
        voice = "hr-HR-GabrijelaNeural"
    else:
        # Fallback English female if Groq fails
        voice = "en-US-AriaNeural"

    tmp_path = tempfile.mktemp(suffix=".mp3")
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(tmp_path)

        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()

        logger.info(f"🔊 edge-tts: Generated {len(audio_bytes)} bytes with voice {voice}")
        return audio_bytes
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def _tts_groq(text: str) -> bytes:
    """Generate TTS audio using Groq Orpheus (English, mature female voice)"""
    response = groq_client.audio.speech.create(
        model="canopylabs/orpheus-v1-english",
        input=text[:10000],
        voice="autumn",
        response_format="mp3"
    )
    audio_bytes = response.read()
    logger.info(f"🔊 Groq Orpheus: Generated {len(audio_bytes)} bytes with voice autumn")
    return audio_bytes


@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech - uses edge-tts for Serbian, Groq Orpheus for English"""
    try:
        text = request.text[:5000] if len(request.text) > 5000 else request.text

        if request.language and request.language.startswith("sr"):
            # Serbian: use edge-tts with Croatian voice (better pronunciation)
            audio_bytes = await _tts_edge(text, request.language)
            voice_used = "hr-HR-GabrijelaNeural"
            language_code = "sr-RS"
        else:
            # English: Groq Orpheus first, fall back to edge-tts
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

        logger.info(f"🔊 TTS: Generated {len(audio_bytes)} bytes for {language_code} via {voice_used}")

        return {
            "success": True,
            "audio": audio_base64,
            "format": "mp3",
            "language": language_code,
            "voice": voice_used
        }

    except Exception as e:
        logger.error(f"❌ TTS error: {e}")
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


@router.get("/voices")
async def list_voices():
    """List available TTS voices"""
    return {
        "voices": [
            {"code": "en-US", "name": "English (US)", "voice": "autumn (female)", "engine": "Groq Orpheus"},
            {"code": "sr-RS", "name": "Serbian", "voice": "Gabrijela (female)", "engine": "edge-tts"},
        ]
    }
