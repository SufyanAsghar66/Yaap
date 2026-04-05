"""
Whisper Speech-to-Text Service Client
Wraps the OpenAI Whisper inference microservice for:
  - Voice training audio validation (detect silence, wrong language)
  - Real-time call transcription (Phase 7)

The Whisper microservice runs whisper large-v3 and exposes:
  POST /transcribe  — transcribe audio, returns {text, language, segments}
  GET  /health      — health check
"""

import logging

import httpx
from django.conf import settings

logger          = logging.getLogger(__name__)
WHISPER_URL     = settings.WHISPER_SERVICE_URL
WHISPER_TIMEOUT = 60.0   # large-v3 on CPU can take up to 45 s


def transcribe(
    audio_bytes: bytes,
    language: str | None = None,
    content_type: str    = "audio/wav",
    filename: str        = "audio.wav",
) -> dict | None:
    """
    Transcribe audio bytes using Whisper.

    Args:
        audio_bytes:  Raw audio file bytes (WAV / MP3 / OGG)
        language:     ISO language code hint (e.g. 'ar'). None = auto-detect.
        content_type: MIME type of audio_bytes
        filename:     Filename sent in multipart

    Returns:
        {
            "text":     str,           # full transcript
            "language": str,           # detected or provided language code
            "segments": list[dict],    # word-level timing segments
            "duration": float,         # audio duration in seconds
        }
        or None on failure.
    """
    try:
        files  = {"audio_file": (filename, audio_bytes, content_type)}
        params = {}
        if language:
            params["language"] = language

        response = httpx.post(
            f"{WHISPER_URL}/transcribe",
            files   = files,
            params  = params,
            timeout = WHISPER_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        logger.info(
            "Whisper transcribed %d bytes: lang=%s duration=%.1fs chars=%d",
            len(audio_bytes),
            data.get("language"),
            data.get("duration", 0),
            len(data.get("text", "")),
        )
        return data

    except httpx.TimeoutException:
        logger.error("Whisper /transcribe timed out after %.0fs", WHISPER_TIMEOUT)
        return None
    except httpx.HTTPStatusError as e:
        logger.error("Whisper /transcribe HTTP error %s: %s", e.response.status_code, e.response.text)
        return None
    except Exception as e:
        logger.exception("Whisper /transcribe unexpected error: %s", e)
        return None


def is_whisper_service_healthy() -> bool:
    try:
        r = httpx.get(f"{WHISPER_URL}/health", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False
