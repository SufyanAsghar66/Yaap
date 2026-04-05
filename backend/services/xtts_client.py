"""
XTTS Microservice Client
Communicates with the Coqui XTTS inference server (a separate Python
microservice running coqui-ai/TTS).

The microservice exposes two endpoints:
  POST /embed   — compute speaker embedding from WAV bytes
  POST /synthesize — synthesize speech from text + embedding (Phase 7)

We use httpx for async-capable HTTP calls from both sync (Celery) and
async (Django Channels) contexts.
"""

import logging
from io import BytesIO
from pathlib import Path

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

XTTS_URL          = settings.XTTS_SERVICE_URL
REQUEST_TIMEOUT   = 120.0    # embedding takes up to 60 s on CPU
SYNTHESIS_TIMEOUT = 30.0


# ─── Speaker Embedding ────────────────────────────────────────────────────────

def compute_speaker_embedding(wav_paths: list[str]) -> list[float] | None:
    """
    Send multiple WAV file bytes to the XTTS microservice and receive back
    a 256-dimensional speaker embedding vector (list of floats).

    Args:
        wav_paths: Local filesystem paths to the VAD-trimmed WAV files.

    Returns:
        List of 256 floats representing the speaker embedding, or None on failure.
    """
    if not wav_paths:
        logger.error("compute_speaker_embedding: no wav_paths provided")
        return None

    try:
        # Build multipart form with all WAV files
        files = []
        for path in wav_paths:
            p = Path(path)
            if not p.exists():
                logger.warning("WAV file not found: %s", path)
                continue
            files.append(("wav_files", (p.name, p.read_bytes(), "audio/wav")))

        if not files:
            logger.error("No valid WAV files to send to XTTS service")
            return None

        response = httpx.post(
            f"{XTTS_URL}/embed",
            files   = files,
            timeout = REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        data      = response.json()
        embedding = data.get("embedding")

        if not embedding or not isinstance(embedding, list):
            logger.error("XTTS /embed returned unexpected payload: %s", data)
            return None

        logger.info(
            "XTTS embedding computed: dim=%d from %d WAV files",
            len(embedding), len(files),
        )
        return embedding

    except httpx.TimeoutException:
        logger.error("XTTS /embed timed out after %.0fs", REQUEST_TIMEOUT)
        return None
    except httpx.HTTPStatusError as e:
        logger.error("XTTS /embed HTTP error: %s — %s", e.response.status_code, e.response.text)
        return None
    except Exception as e:
        logger.exception("XTTS /embed unexpected error: %s", e)
        return None


# ─── Speech Synthesis (Phase 7 — stub here for wiring) ───────────────────────

def synthesize_speech(
    text: str,
    embedding: list[float],
    language: str,
    speed: float = 1.0,
) -> bytes | None:
    """
    Synthesize speech from text using a pre-computed speaker embedding.
    Returns raw WAV bytes, or None on failure.
    Used in Phase 7 (call translation pipeline).
    """
    try:
        response = httpx.post(
            f"{XTTS_URL}/synthesize",
            json    = {
                "text":      text,
                "embedding": embedding,
                "language":  language,
                "speed":     speed,
            },
            timeout = SYNTHESIS_TIMEOUT,
        )
        response.raise_for_status()
        logger.info("XTTS synthesis: %d chars → %d bytes WAV", len(text), len(response.content))
        return response.content

    except httpx.TimeoutException:
        logger.error("XTTS /synthesize timed out")
        return None
    except httpx.HTTPStatusError as e:
        logger.error("XTTS /synthesize HTTP error: %s", e.response.status_code)
        return None
    except Exception as e:
        logger.exception("XTTS /synthesize unexpected error: %s", e)
        return None


# ─── Health Check ─────────────────────────────────────────────────────────────

def is_xtts_service_healthy() -> bool:
    """Ping the XTTS microservice health endpoint."""
    try:
        r = httpx.get(f"{XTTS_URL}/health", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False
