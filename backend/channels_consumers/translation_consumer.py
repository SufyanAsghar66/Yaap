"""
Media Relay Service
Coordinates the real-time audio translation pipeline for active voice calls.

Architecture:
  Kotlin app (caller) ──WebRTC──► media relay ──► Whisper STT
                                                      │
                                                  Translation
                                                      │
                                                  XTTS synthesis
                                                      │
                  Kotlin app (callee) ◄──WebRTC── media relay

In Phase 7 we implement:
  1. A Django Channels consumer that receives raw audio frames via WebSocket
     from each peer (the Kotlin app streams mic audio here in addition to
     the WebRTC peer connection)
  2. The pipeline: audio frames → buffer → Whisper → translate → XTTS → inject

The injected audio is sent BACK to the callee via a separate WebSocket
channel, and the Kotlin app mixes the translated audio into the speaker
output (replacing or overlaying the original voice stream).

For production at scale, this should be replaced by a Livekit SFU
with a server-side audio track subscriber. The WebSocket approach
implemented here is sufficient for MVP and up to ~50 concurrent calls.

WebSocket path:
  ws://host/ws/translate/<room_id>/<direction>/?token=<jwt>
  direction: "caller_audio" | "callee_audio"

Audio frames sent by client:
  Binary WebSocket frames: raw PCM 16-bit mono 16 kHz chunks
  Frame size: 1280 bytes = 40 ms of audio (optimal for Whisper + VAD)

Events sent by server (JSON):
  { "type": "translated_audio", "payload": { "audio_b64": "<base64 WAV>" } }
  { "type": "transcript",       "payload": { "text": "...", "lang": "en" } }
  { "type": "translation",      "payload": { "text": "...", "lang": "ar" } }
  { "type": "pipeline_error",   "payload": { "message": "..." } }
"""

import asyncio
import base64
import logging
import struct
import wave
from io import BytesIO

from channels.db import database_sync_to_async
from channels_consumers.base_consumer import BaseConsumer

logger = logging.getLogger(__name__)

# Audio buffering constants
FRAME_BYTES       = 1280          # 40 ms @ 16 kHz 16-bit mono
BUFFER_FRAMES     = 25            # 25 × 40 ms = 1 000 ms (1 second) per chunk
SAMPLE_RATE       = 16_000
SILENCE_THRESHOLD = 200           # RMS threshold below which we skip synthesis


class TranslationConsumer(BaseConsumer):
    """
    ws://host/ws/translate/<room_id>/<direction>/?token=<jwt>

    Receives raw PCM audio from one peer, runs the full translation pipeline,
    and emits synthesized audio + transcript events back to the same connection.
    The Kotlin app then plays the synthesized audio for the listener.
    """

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self):
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.room_id   = self.scope["url_route"]["kwargs"]["room_id"]
        self.direction = self.scope["url_route"]["kwargs"]["direction"]

        if self.direction not in ("caller_audio", "callee_audio"):
            await self.close(code=4002)
            return

        room = await self._load_room()
        if not room:
            await self.close(code=4003)
            return

        self.room           = room
        self.audio_buffer   = bytearray()
        self.frames_buffered = 0
        self.pipeline_lock  = asyncio.Lock()

        # Determine source and target language from room
        if self.direction == "caller_audio":
            self.source_lang = room.caller_language
            self.target_lang = room.callee_language
            self.speaker_id  = str(room.callee_id)   # whose voice to clone for synthesis
        else:
            self.source_lang = room.callee_language
            self.target_lang = room.caller_language
            self.speaker_id  = str(room.caller_id)

        # Pre-load speaker embedding for fast synthesis
        self.speaker_embedding = await self._load_embedding(self.speaker_id)

        await self.accept()
        logger.info(
            "TranslationConsumer connected: user=%s room=%s dir=%s %s→%s",
            self.user.id, self.room_id, self.direction,
            self.source_lang, self.target_lang,
        )

    async def disconnect(self, close_code):
        logger.info(
            "TranslationConsumer disconnected: user=%s room=%s code=%s",
            self.user.id, self.room_id, close_code,
        )

    # ── Receive audio frames ───────────────────────────────────────────────────

    async def receive(self, text_data=None, bytes_data=None):
        """
        Receive binary PCM frames from the Kotlin client.
        Buffer until we have BUFFER_FRAMES × FRAME_BYTES, then pipeline.
        """
        if bytes_data:
            await self._handle_audio_frame(bytes_data)
        elif text_data:
            # Control messages (e.g. flush, pause)
            import json
            try:
                msg = json.loads(text_data)
                if msg.get("type") == "flush":
                    await self._flush_buffer()
            except Exception:
                pass

    async def _handle_audio_frame(self, frame: bytes):
        """Accumulate PCM frames into buffer. Trigger pipeline when full."""
        self.audio_buffer.extend(frame)
        self.frames_buffered += 1

        if self.frames_buffered >= BUFFER_FRAMES:
            async with self.pipeline_lock:
                chunk = bytes(self.audio_buffer)
                self.audio_buffer.clear()
                self.frames_buffered = 0

            # Run pipeline in background so we don't block frame reception
            asyncio.create_task(self._run_pipeline(chunk))

    async def _flush_buffer(self):
        """Process whatever is in the buffer immediately (end-of-utterance signal)."""
        if self.audio_buffer:
            async with self.pipeline_lock:
                chunk = bytes(self.audio_buffer)
                self.audio_buffer.clear()
                self.frames_buffered = 0
            asyncio.create_task(self._run_pipeline(chunk))

    # ── Translation Pipeline ──────────────────────────────────────────────────

    async def _run_pipeline(self, pcm_chunk: bytes):
        """
        Full pipeline: PCM → VAD check → Whisper STT → translate → XTTS → emit.
        Runs asynchronously so it doesn't block audio frame intake.
        """
        # ── 1. Skip silent chunks ──────────────────────────────────────────────
        if _is_silent(pcm_chunk):
            return

        # ── 2. If source == target, no translation needed ──────────────────────
        if self.source_lang == self.target_lang:
            return

        # ── 3. Whisper STT ────────────────────────────────────────────────────
        wav_bytes  = _pcm_to_wav(pcm_chunk)
        transcript = await asyncio.get_event_loop().run_in_executor(
            None, _whisper_transcribe, wav_bytes, self.source_lang
        )

        if not transcript or not transcript.strip():
            logger.debug("Whisper returned empty transcript — skipping")
            return

        # Emit transcript to client (for UI display)
        await self.send_event("transcript", {
            "text":     transcript,
            "language": self.source_lang,
        })

        # ── 4. Translate ───────────────────────────────────────────────────────
        translated = await asyncio.get_event_loop().run_in_executor(
            None, _translate_text, transcript, self.source_lang, self.target_lang
        )

        if not translated:
            logger.warning("Translation returned empty for: %s", transcript[:60])
            return

        await self.send_event("translation", {
            "text":     translated,
            "language": self.target_lang,
        })

        # ── 5. XTTS Synthesis ─────────────────────────────────────────────────
        if not self.speaker_embedding:
            logger.warning("No speaker embedding for %s — skipping synthesis", self.speaker_id)
            return

        synthesized_wav = await asyncio.get_event_loop().run_in_executor(
            None, _synthesize, translated, self.speaker_embedding, self.target_lang
        )

        if not synthesized_wav:
            logger.warning("XTTS synthesis returned no audio")
            return

        # ── 6. Emit synthesized audio to client ────────────────────────────────
        audio_b64 = base64.b64encode(synthesized_wav).decode("utf-8")
        await self.send_event("translated_audio", {
            "audio_b64":   audio_b64,
            "language":    self.target_lang,
            "source_text": transcript,
            "target_text": translated,
            "sample_rate": SAMPLE_RATE,
            "format":      "wav",
        })

        logger.info(
            "Translation pipeline complete: %s→%s '%s'→'%s' (%d bytes WAV)",
            self.source_lang, self.target_lang,
            transcript[:40], translated[:40], len(synthesized_wav),
        )

    # ── DB helpers ────────────────────────────────────────────────────────────

    @database_sync_to_async
    def _load_room(self):
        from apps.calls.models import CallRoom
        from django.db.models import Q
        try:
            return CallRoom.objects.select_related("caller", "callee").get(
                room_id = self.room_id,
            )
        except CallRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def _load_embedding(self, user_id: str) -> list | None:
        """Load the pre-computed XTTS speaker embedding for the target speaker."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
            if user.voice_embedding and isinstance(user.voice_embedding, list):
                logger.debug("Loaded embedding dim=%d for user=%s", len(user.voice_embedding), user_id)
                return user.voice_embedding
            logger.warning("No voice embedding for user %s — synthesis will be skipped", user_id)
            return None
        except User.DoesNotExist:
            return None


# ─── Pipeline Functions (sync — run in executor) ──────────────────────────────

def _is_silent(pcm_bytes: bytes, threshold: int = SILENCE_THRESHOLD) -> bool:
    """Return True if RMS energy of the chunk is below silence threshold."""
    if not pcm_bytes:
        return True
    try:
        samples = [
            struct.unpack_from("<h", pcm_bytes, i)[0]
            for i in range(0, len(pcm_bytes) - 1, 2)
        ]
        if not samples:
            return True
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
        return rms < threshold
    except Exception:
        return False


def _pcm_to_wav(pcm_bytes: bytes) -> bytes:
    """Wrap raw PCM bytes into a WAV container for Whisper."""
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)       # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def _whisper_transcribe(wav_bytes: bytes, language: str) -> str | None:
    """Call Whisper STT microservice synchronously."""
    from services.whisper_service import transcribe
    result = transcribe(wav_bytes, language=language, filename="chunk.wav")
    if result:
        return result.get("text", "").strip()
    return None


def _translate_text(text: str, source_lang: str, target_lang: str) -> str | None:
    """Translate text using DeepL/Helsinki pipeline."""
    from services.translation import translate
    try:
        return translate(text, target_language=target_lang, source_language=source_lang)
    except Exception as e:
        logger.error("Translation error in pipeline: %s", e)
        return None


def _synthesize(text: str, embedding: list, language: str) -> bytes | None:
    """Synthesize speech using XTTS microservice."""
    from services.xtts_client import synthesize_speech
    return synthesize_speech(text=text, embedding=embedding, language=language)
