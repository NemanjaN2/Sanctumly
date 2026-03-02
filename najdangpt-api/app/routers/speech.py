"""
Speech routes - Speech-to-Text and Text-to-Speech
"""
import logging
import base64
import io
import subprocess
import tempfile
import os
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from google.cloud import speech
from google.cloud import texttospeech

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/speech", tags=["Speech"])


class TTSRequest(BaseModel):
    text: str
    language: Optional[str] = "en-US"
    voice_gender: Optional[str] = "female"


def convert_to_wav(audio_content: bytes, input_format: str) -> bytes:
    """Convert audio to WAV format using ffmpeg"""
    try:
        with tempfile.NamedTemporaryFile(suffix=f'.{input_format}', delete=False) as input_file:
            input_file.write(audio_content)
            input_path = input_file.name
        
        output_path = input_path.replace(f'.{input_format}', '.wav')
        
        # Convert to 16kHz mono WAV (optimal for Google Speech)
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-ar', '16000',  # 16kHz sample rate
            '-ac', '1',      # Mono
            '-f', 'wav',     # WAV format
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"❌ ffmpeg error: {result.stderr.decode()}")
            return None
        
        with open(output_path, 'rb') as f:
            wav_content = f.read()
        
        # Cleanup temp files
        os.unlink(input_path)
        os.unlink(output_path)
        
        logger.info(f"✅ Converted {input_format} to WAV: {len(audio_content)} -> {len(wav_content)} bytes")
        return wav_content
        
    except Exception as e:
        logger.error(f"❌ Conversion error: {e}")
        return None


def detect_audio_config(filename: str, content_type: str, audio_content: bytes):
    """Detect the appropriate audio encoding and sample rate based on file info"""
    
    filename_lower = filename.lower() if filename else ""
    content_type_lower = content_type.lower() if content_type else ""
    
    logger.info(f"🎵 Audio detection - filename: {filename}, content_type: {content_type}, size: {len(audio_content)} bytes")
    
    # Check for webm/opus (most common from browsers)
    if "webm" in filename_lower or "webm" in content_type_lower:
        return speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            sample_rate_hertz=48000,
            language_code="en-US",
            enable_automatic_punctuation=True,
            model="latest_long",
            alternative_language_codes=["sr-RS"],
        ), None
    
    # Check for mp4/m4a (iOS/macOS) - needs conversion
    if "m4a" in filename_lower or "mp4" in filename_lower or "m4a" in content_type_lower or "mp4" in content_type_lower:
        # Convert M4A to WAV
        wav_content = convert_to_wav(audio_content, 'm4a')
        if wav_content:
            return speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="en-US",
                enable_automatic_punctuation=True,
                model="latest_long",
                alternative_language_codes=["sr-RS"],
            ), wav_content
        else:
            # Fallback: try with encoding unspecified
            return speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED,
                sample_rate_hertz=44100,
                language_code="en-US",
                enable_automatic_punctuation=True,
                model="latest_long",
                alternative_language_codes=["sr-RS"],
            ), None
    
    # Check for wav
    if "wav" in filename_lower or "wav" in content_type_lower:
        return speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=True,
            model="latest_long",
            alternative_language_codes=["sr-RS"],
        ), None
    
    # Check for mp3
    if "mp3" in filename_lower or "mpeg" in content_type_lower:
        return speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=True,
            model="latest_long",
            alternative_language_codes=["sr-RS"],
        ), None
    
    # Check for ogg/opus
    if "ogg" in filename_lower or "opus" in filename_lower or "ogg" in content_type_lower:
        return speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            sample_rate_hertz=48000,
            language_code="en-US",
            enable_automatic_punctuation=True,
            model="latest_long",
            alternative_language_codes=["sr-RS"],
        ), None
    
    # Check for flac
    if "flac" in filename_lower or "flac" in content_type_lower:
        return speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
            language_code="en-US",
            enable_automatic_punctuation=True,
            model="latest_long",
            alternative_language_codes=["sr-RS"],
        ), None
    
    # Default: Let Google auto-detect (works for many formats)
    logger.warning(f"⚠️ Unknown audio format, using auto-detection")
    return speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED,
        language_code="en-US",
        enable_automatic_punctuation=True,
        model="latest_long",
        alternative_language_codes=["sr-RS"],
    ), None


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe audio to text using Google Speech-to-Text"""
    try:
        audio_content = await file.read()
        
        # Log file details for debugging
        logger.info(f"🎤 Received audio: {file.filename}, type: {file.content_type}, size: {len(audio_content)} bytes")
        
        # Check minimum size
        if len(audio_content) < 1000:
            logger.warning(f"⚠️ Audio too small: {len(audio_content)} bytes")
            return {
                "success": False,
                "transcript": "",
                "error": "Recording too short"
            }
        
        client = speech.SpeechClient()
        
        # Auto-detect audio configuration (may convert to WAV)
        config, converted_audio = detect_audio_config(file.filename, file.content_type, audio_content)
        
        # Use converted audio if available, otherwise use original
        final_audio = converted_audio if converted_audio else audio_content
        
        audio = speech.RecognitionAudio(content=final_audio)
        
        logger.info(f"🎵 Using encoding: {config.encoding}, sample_rate: {config.sample_rate_hertz}, audio_size: {len(final_audio)}")
        
        response = client.recognize(config=config, audio=audio)
        
        transcript = ""
        confidence = 0.0
        for result in response.results:
            if result.alternatives:
                transcript += result.alternatives[0].transcript + " "
                confidence = max(confidence, result.alternatives[0].confidence)
        
        transcript = transcript.strip()
        
        if not transcript:
            logger.warning("⚠️ No speech detected in audio")
            return {
                "success": False,
                "transcript": "",
                "error": "No speech detected"
            }
        
        logger.info(f"🎤 Transcribed: '{transcript[:50]}...' (confidence: {confidence:.2f})")
        
        return {
            "success": True,
            "transcript": transcript,
            "confidence": confidence
        }
        
    except Exception as e:
        logger.error(f"❌ Transcription error: {e}")
        # Return a structured error instead of raising HTTPException
        return {
            "success": False,
            "transcript": "",
            "error": str(e)
        }


@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using Google Cloud TTS"""
    try:
        client = texttospeech.TextToSpeechClient()
        
        # Truncate very long text (TTS has limits)
        text = request.text[:5000] if len(request.text) > 5000 else request.text
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        if request.language.startswith("sr"):
            language_code = "sr-RS"
            voice_name = "sr-RS-Standard-A"
        else:
            language_code = "en-US"
            if request.voice_gender == "male":
                voice_name = "en-US-WaveNet-D"
            else:
                voice_name = "en-US-WaveNet-F"
        
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
            pitch=0.0
        )
        
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        audio_base64 = base64.b64encode(response.audio_content).decode('utf-8')
        
        logger.info(f"🔊 TTS: Generated {len(response.audio_content)} bytes for {language_code}")
        
        return {
            "success": True,
            "audio": audio_base64,
            "format": "mp3",
            "language": language_code,
            "voice": voice_name
        }
        
    except Exception as e:
        logger.error(f"❌ TTS error: {e}")
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


@router.get("/voices")
async def list_voices():
    """List available TTS voices"""
    return {
        "voices": [
            {"code": "en-US", "name": "English (US)", "genders": ["male", "female"]},
            {"code": "en-GB", "name": "English (UK)", "genders": ["male", "female"]},
            {"code": "sr-RS", "name": "Serbian", "genders": ["female"]},
        ]
    }
