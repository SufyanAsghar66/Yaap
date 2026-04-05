# YAAP AI Microservices

## Overview

Two standalone FastAPI microservices handle the AI workloads:

| Service | Port | Purpose |
|---------|------|---------|
| `xtts_service` | 8001 | Speaker embedding + speech synthesis (Coqui XTTS v2) |
| `whisper_service` | 8002 | Speech-to-text transcription (OpenAI Whisper large-v3) |

Both are **internal-only** — never exposed to the public internet.
Django reaches them via `XTTS_SERVICE_URL` and `WHISPER_SERVICE_URL` env vars.

## Running Locally (Development)

```bash
# XTTS service (requires GPU for real-time performance)
cd microservices
pip install -r requirements_xtts.txt
python xtts_service.py

# Whisper service
pip install -r requirements_whisper.txt
WHISPER_MODEL=small python whisper_service.py  # use 'small' on CPU
```

## Running via Docker

```bash
docker compose up xtts_service whisper_service
```

GPU support requires `nvidia-docker` and the NVIDIA Container Toolkit.

## Audio Translation Pipeline Flow

```
Kotlin app (caller mic) ──binary PCM──► ws/translate/<room_id>/caller_audio/
                                              │
                                         Buffer 25 frames (1 second)
                                              │
                                         Silence detection (skip if quiet)
                                              │
                                         Whisper STT → transcript text
                                              │
                                         DeepL / Helsinki-NLP translation
                                              │
                                         XTTS synthesis (callee's voice)
                                              │
                              ◄── base64 WAV event ── TranslationConsumer
                                              │
                         Kotlin app mixes synthesized audio into speaker output
```

## Frame Format

The Kotlin app sends raw PCM audio as binary WebSocket frames:
- Sample rate: 16,000 Hz
- Channels: 1 (mono)
- Bit depth: 16-bit signed little-endian
- Frame size: 1,280 bytes = 40 ms per frame
- Buffer: 25 frames = 1 second before pipeline triggers

## Latency Budget

| Step | Target | Notes |
|------|--------|-------|
| Network (app → server) | < 50 ms | WebSocket |
| Buffering | 1,000 ms | 25 × 40 ms frames |
| Whisper STT | < 200 ms | GPU, small model |
| Translation | < 100 ms | DeepL API or cached |
| XTTS synthesis | < 500 ms | GPU required |
| Network (server → app) | < 50 ms | WebSocket |
| **Total** | **< 1,900 ms** | ~2 seconds end-to-end |

## Performance Notes

- Use Whisper `small` or `medium` for < 500 ms STT on GPU
- XTTS requires a dedicated GPU — do not share with Whisper
- For > 50 concurrent translated calls, migrate to Livekit SFU
  with a dedicated GPU cluster for XTTS
