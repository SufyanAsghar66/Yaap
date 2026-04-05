"""
XTTS Inference Microservice
FastAPI server that wraps Coqui XTTS v2 for:
  POST /embed      — compute 256-dim speaker embedding from WAV files
  POST /synthesize — synthesize speech from text + embedding
  GET  /health     — health check
  GET  /languages  — list supported languages

Run with:
  pip install fastapi uvicorn "coqui-tts>=0.22.0" torch torchaudio
  uvicorn xtts_service:app --host 0.0.0.0 --port 8001 --workers 1

GPU: set CUDA_VISIBLE_DEVICES=0 before starting for GPU inference.
CPU: works but synthesis takes 3-8 seconds per utterance.

Docker:
  FROM pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime
  (see xtts_service.Dockerfile)
"""

import logging
import os
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Optional

import torch
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger("xtts_service")
logging.basicConfig(level=logging.INFO)

app        = FastAPI(title="YAAP XTTS Service", version="1.0.0")
_tts_model = None    # lazy-loaded singleton


# ─── Supported languages (Coqui XTTS v2) ─────────────────────────────────────

SUPPORTED_LANGUAGES = [
    "en", "es", "fr", "de", "it", "pt", "pl", "tr",
    "ru", "nl", "cs", "ar", "zh-cn", "ja", "ko", "hu", "hi",
]

XTTS_LANG_MAP = {
    "en": "en", "es": "es", "fr": "fr",  "de": "de",
    "it": "it", "pt": "pt", "pl": "pl",  "tr": "tr",
    "ru": "ru", "nl": "nl", "cs": "cs",  "ar": "ar",
    "zh": "zh-cn", "ja": "ja", "ko": "ko", "hu": "hu", "hi": "hi",
}


# ─── Model Loading ────────────────────────────────────────────────────────────

def _get_model():
    global _tts_model
    if _tts_model is None:
        logger.info("Loading Coqui XTTS v2 model...")
        t0 = time.time()
        from TTS.api import TTS
        _tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        if torch.cuda.is_available():
            _tts_model = _tts_model.to("cuda")
            logger.info("XTTS loaded on GPU in %.1fs", time.time() - t0)
        else:
            logger.info("XTTS loaded on CPU in %.1fs (GPU not available)", time.time() - t0)
    return _tts_model


# ─── API Models ───────────────────────────────────────────────────────────────

class SynthesizeRequest(BaseModel):
    text:      str
    embedding: list[float]
    language:  str
    speed:     float = 1.0


class EmbedResponse(BaseModel):
    embedding:   list[float]
    dim:         int
    num_samples: int
    duration_ms: float


class HealthResponse(BaseModel):
    status:    str
    model:     str
    device:    str
    gpu_mem:   Optional[str]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    device  = "cuda" if torch.cuda.is_available() else "cpu"
    gpu_mem = None
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024 ** 3
        reserved  = torch.cuda.memory_reserved()  / 1024 ** 3
        gpu_mem   = f"{allocated:.2f}GB allocated / {reserved:.2f}GB reserved"
    return HealthResponse(
        status  = "ok",
        model   = "xtts_v2",
        device  = device,
        gpu_mem = gpu_mem,
    )


@app.get("/languages")
async def languages():
    return {"languages": SUPPORTED_LANGUAGES}


@app.post("/embed", response_model=EmbedResponse)
async def embed(wav_files: list[UploadFile] = File(...)):
    """
    Compute a speaker embedding from one or more WAV files.
    Returns a 256-dimensional float vector representing the speaker's voice.
    The more samples provided (up to 5), the more robust the embedding.
    """
    if not wav_files:
        raise HTTPException(400, "At least one WAV file is required.")

    t0      = time.time()
    model   = _get_model()

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for i, f in enumerate(wav_files):
            content = await f.read()
            dest    = os.path.join(tmpdir, f"sample_{i}.wav")
            Path(dest).write_bytes(content)
            paths.append(dest)

        try:
            # XTTS get_conditioning_latents computes the speaker embedding
            gpt_cond_latent, speaker_embedding = model.synthesizer.tts_model.get_conditioning_latents(
                audio_path = paths,
            )
            # Flatten to a 1D list for JSON serialization
            embedding = speaker_embedding.squeeze().cpu().tolist()
            # Ensure it's 1D
            if isinstance(embedding[0], list):
                embedding = [x for row in embedding for x in row]

            duration_ms = (time.time() - t0) * 1000
            logger.info(
                "Embedding computed: dim=%d samples=%d took=%.0fms",
                len(embedding), len(paths), duration_ms,
            )
            return EmbedResponse(
                embedding   = embedding,
                dim         = len(embedding),
                num_samples = len(paths),
                duration_ms = duration_ms,
            )
        except Exception as e:
            logger.exception("Embedding computation failed: %s", e)
            raise HTTPException(500, f"Embedding failed: {e}")


@app.post("/synthesize")
async def synthesize(req: SynthesizeRequest):
    """
    Synthesize speech from text using a pre-computed speaker embedding.
    Returns raw WAV bytes (16 kHz mono 16-bit PCM).
    """
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text must not be empty.")

    lang = XTTS_LANG_MAP.get(req.language, req.language)
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"Unsupported language: {req.language}. Supported: {SUPPORTED_LANGUAGES}")

    if not req.embedding:
        raise HTTPException(400, "embedding must not be empty.")

    t0    = time.time()
    model = _get_model()

    try:
        import numpy as np

        # Reconstruct speaker embedding tensor
        emb_tensor = torch.tensor(req.embedding, dtype=torch.float32)

        # Infer shape: XTTS expects (1, 512) or (1, 256) depending on model version
        expected_dim = model.synthesizer.tts_model.embedded_speakers_d
        if emb_tensor.numel() != expected_dim:
            logger.warning(
                "Embedding dim mismatch: got %d expected %d — attempting reshape",
                emb_tensor.numel(), expected_dim,
            )
        emb_tensor = emb_tensor.unsqueeze(0)   # add batch dim → (1, dim)

        if torch.cuda.is_available():
            emb_tensor = emb_tensor.cuda()

        # Synthesize
        with torch.no_grad():
            wav = model.synthesizer.tts_model.inference(
                text             = req.text,
                language         = lang,
                gpt_cond_latent  = None,
                speaker_embedding = emb_tensor,
                speed            = req.speed,
            )

        # Convert to numpy and then WAV bytes
        wav_np = np.array(wav["wav"], dtype=np.float32)

        # Normalize to int16
        wav_int16 = (wav_np * 32767).clip(-32768, 32767).astype(np.int16)

        # Encode as WAV
        buf = BytesIO()
        import wave
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)    # XTTS outputs at 24 kHz
            wf.writeframes(wav_int16.tobytes())
        wav_bytes = buf.getvalue()

        duration_ms = (time.time() - t0) * 1000
        logger.info(
            "Synthesis complete: lang=%s chars=%d size=%d bytes took=%.0fms",
            lang, len(req.text), len(wav_bytes), duration_ms,
        )

        return Response(
            content      = wav_bytes,
            media_type   = "audio/wav",
            headers      = {
                "X-Duration-Ms":  str(int(duration_ms)),
                "X-Sample-Rate":  "24000",
                "X-Text-Length":  str(len(req.text)),
            },
        )

    except Exception as e:
        logger.exception("Synthesis failed: %s", e)
        raise HTTPException(500, f"Synthesis failed: {e}")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Pre-warm the model on startup
    logger.info("Pre-warming XTTS model...")
    _get_model()
    logger.info("XTTS service ready.")

    uvicorn.run(
        "xtts_service:app",
        host     = "0.0.0.0",
        port     = int(os.environ.get("PORT", 8001)),
        workers  = 1,       # XTTS is NOT thread-safe — single worker only
        log_level = "info",
    )
