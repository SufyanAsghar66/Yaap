# ─── Whisper STT Microservice Dockerfile ─────────────────────────────────────
# GPU strongly recommended for real-time call transcription
# Whisper large-v3 on GPU: ~300 ms per 1s audio
# Whisper large-v3 on CPU: ~3-5 s per 1s audio (use 'small' for CPU)

FROM pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime

LABEL description="YAAP Whisper STT microservice"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg      \
    curl        \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY microservices/requirements_whisper.txt .
RUN pip install --no-cache-dir -r requirements_whisper.txt

COPY microservices/whisper_service.py .

# Pre-download Whisper model
ARG WHISPER_MODEL=large-v3
ENV WHISPER_MODEL=${WHISPER_MODEL}

RUN python -c "import whisper; whisper.load_model('${WHISPER_MODEL}')" \
    || echo "Model download will happen at runtime"

ENV PORT=8002
EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

CMD ["python", "whisper_service.py"]
