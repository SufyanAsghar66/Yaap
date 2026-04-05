"""
Whisper STT Microservice
FastAPI server wrapping OpenAI Whisper large-v3 for:
  POST /transcribe  — transcribe audio to text
  GET  /health      — health check
  GET  /languages   — supported language list

Run with:
  pip install fastapi uvicorn openai-whisper ffmpeg-python torch
  uvicorn whisper_service:app --host 0.0.0.0 --port 8002 --workers 1

Notes:
  - Whisper large-v3 requires ~3 GB GPU VRAM or ~6 GB RAM on CPU
  - For real-time calls, use whisper.cpp with small/medium model for < 500 ms latency
  - Set MODEL_SIZE env var: tiny/base/small/medium/large-v3 (default: large-v3)
"""

import io
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger     = logging.getLogger("whisper_service")
logging.basicConfig(level=logging.INFO)

app        = FastAPI(title="YAAP Whisper STT Service", version="1.0.0")
_model     = None
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "large-v3")


# ─── Supported Languages ──────────────────────────────────────────────────────

WHISPER_LANGUAGES = {
    "en": "english",   "es": "spanish",    "fr": "french",
    "de": "german",    "it": "italian",    "pt": "portuguese",
    "pl": "polish",    "tr": "turkish",    "ru": "russian",
    "nl": "dutch",     "cs": "czech",      "ar": "arabic",
    "zh": "chinese",   "ja": "japanese",   "ko": "korean",
    "hu": "hungarian", "hi": "hindi",
}


# ─── Model Loading ────────────────────────────────────────────────────────────

def _get_model():
    global _model
    if _model is None:
        import whisper
        logger.info("Loading Whisper %s model...", MODEL_SIZE)
        t0     = time.time()
        _model = whisper.load_model(MODEL_SIZE)
        logger.info("Whisper %s loaded in %.1fs", MODEL_SIZE, time.time() - t0)
    return _model


# ─── Response Models ──────────────────────────────────────────────────────────

class TranscriptSegment(BaseModel):
    start: float
    end:   float
    text:  str


class TranscribeResponse(BaseModel):
    text:     str
    language: str
    duration: float
    segments: list[TranscriptSegment]
    model:    str
    took_ms:  float


class HealthResponse(BaseModel):
    status: str
    model:  str
    device: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return HealthResponse(status="ok", model=MODEL_SIZE, device=device)


@app.get("/languages")
async def languages():
    return {"languages": list(WHISPER_LANGUAGES.keys())}


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    audio_file: UploadFile = File(...),
    language:   Optional[str] = Query(None, description="ISO language code hint (e.g. 'ar'). None = auto-detect."),
    task:       str            = Query("transcribe", description="'transcribe' or 'translate' (translate → English)"),
):
    """
    Transcribe an audio file using Whisper.
    Accepts WAV, MP3, OGG, M4A, WebM.
    Returns full transcript, detected language, duration, and word segments.
    """
    if task not in ("transcribe", "translate"):
        raise HTTPException(400, "task must be 'transcribe' or 'translate'.")

    content = await audio_file.read()
    if not content:
        raise HTTPException(400, "Audio file is empty.")
    if len(content) > 100 * 1024 * 1024:    # 100 MB hard limit
        raise HTTPException(413, "Audio file too large (max 100 MB).")

    t0    = time.time()
    model = _get_model()

    # Write to temp file (Whisper needs a file path for ffmpeg decoding)
    suffix = Path(audio_file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        whisper_lang = None
        if language:
            whisper_lang = WHISPER_LANGUAGES.get(language, language)

        result = model.transcribe(
            tmp_path,
            language           = whisper_lang,
            task               = task,
            word_timestamps    = False,
            verbose            = False,
            condition_on_previous_text = True,
            temperature        = 0.0,   # greedy decoding for consistency
            compression_ratio_threshold = 2.4,
            no_speech_threshold = 0.6,
        )

        took_ms  = (time.time() - t0) * 1000
        detected = result.get("language", language or "unknown")

        segments = [
            TranscriptSegment(
                start = seg["start"],
                end   = seg["end"],
                text  = seg["text"].strip(),
            )
            for seg in result.get("segments", [])
        ]

        transcript = result.get("text", "").strip()

        logger.info(
            "Transcribed: lang=%s chars=%d segments=%d took=%.0fms",
            detected, len(transcript), len(segments), took_ms,
        )

        return TranscribeResponse(
            text     = transcript,
            language = detected,
            duration = result.get("segments", [{}])[-1].get("end", 0) if result.get("segments") else 0,
            segments = segments,
            model    = MODEL_SIZE,
            took_ms  = took_ms,
        )

    except Exception as e:
        logger.exception("Transcription failed: %s", e)
        raise HTTPException(500, f"Transcription failed: {e}")

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ─── Batch endpoint (for voice training validation) ───────────────────────────

@app.post("/batch-transcribe")
async def batch_transcribe(
    audio_files: list[UploadFile] = File(...),
    language:    Optional[str]    = Query(None),
):
    """
    Transcribe multiple audio files (used during voice training to validate
    that the user is actually speaking the correct language).
    Returns list of transcripts in the same order as input files.
    """
    results = []
    for f in audio_files:
        content = await f.read()
        suffix  = Path(f.filename or "audio.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            model  = _get_model()
            result = model.transcribe(tmp_path, language=language, task="transcribe", temperature=0.0)
            results.append({
                "filename": f.filename,
                "text":     result.get("text", "").strip(),
                "language": result.get("language", "unknown"),
            })
        except Exception as e:
            results.append({"filename": f.filename, "error": str(e)})
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    return {"results": results}


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Pre-warming Whisper %s model...", MODEL_SIZE)
    _get_model()
    logger.info("Whisper service ready.")

    uvicorn.run(
        "whisper_service:app",
        host      = "0.0.0.0",
        port      = int(os.environ.get("PORT", 8002)),
        workers   = 1,
        log_level = "info",
    )
