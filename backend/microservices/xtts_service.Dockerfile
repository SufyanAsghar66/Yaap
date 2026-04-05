# ─── XTTS Inference Microservice Dockerfile ───────────────────────────────────
# Requires NVIDIA GPU for real-time synthesis (< 800 ms target)
# CPU inference works but takes 3-8 seconds per utterance

FROM pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime

LABEL description="YAAP XTTS v2 inference microservice"

# System deps: ffmpeg for audio I/O, build tools for TTS
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg          \
    libsndfile1     \
    build-essential \
    git             \
    curl            \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY microservices/requirements_xtts.txt .
RUN pip install --no-cache-dir -r requirements_xtts.txt

# Copy service code
COPY microservices/xtts_service.py .

# Pre-download XTTS model at build time (cache in image layer)
# This avoids slow downloads on container start
RUN python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')" \
    || echo "Model download will happen at runtime"

ENV PORT=8001
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "xtts_service.py"]
