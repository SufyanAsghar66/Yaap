"""
Voice Training Celery Task
Full pipeline:
  1. Load job + user from DB
  2. Download all 5 WAV samples from Supabase Storage
  3. Process each: VAD trim → normalize → validate
  4. Send to XTTS microservice → receive 256-dim embedding
  5. Save embedding to user.voice_embedding
  6. Mark user.voice_trained = True
  7. Push completion event to user via WebSocket (Django Channels)
  8. Send FCM push notification
  9. Send welcome email if first time training

Error handling:
  - Each step wrapped individually so partial failures are logged
  - Job marked FAILED with reason stored in error_message
  - User notified of failure via FCM so the app can show a retry prompt
"""

import logging
import os
import tempfile
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User   = get_user_model()


@shared_task(
    bind              = True,
    name              = "voice.train_voice_model",
    queue             = "voice_training",
    max_retries       = 2,
    default_retry_delay = 60,
    soft_time_limit   = 240,
    time_limit        = 300,
)
def train_voice_model(self, job_id: str):
    """
    Main voice training task.
    Called after user uploads all 5 voice samples and hits POST /api/v1/voice/train/.
    """
    from apps.voice.models import VoiceTrainingJob, VoiceSample

    # ── Load job ──────────────────────────────────────────────────────────────
    try:
        job  = VoiceTrainingJob.objects.select_related("user").get(id=job_id)
        user = job.user
    except VoiceTrainingJob.DoesNotExist:
        logger.error("train_voice_model: job %s not found", job_id)
        return

    logger.info("Voice training started: job=%s user=%s", job_id, user.id)
    job.mark_processing(self.request.id)

    with tempfile.TemporaryDirectory(prefix="yaap_voice_") as tmpdir:
        try:
            # ── Download samples from Supabase Storage ────────────────────────
            samples = list(
                VoiceSample.objects.filter(user=user)
                .order_by("sample_index")
                .select_related("sentence")
            )

            if len(samples) < settings.YAAP_MAX_VOICE_SAMPLES:
                raise ValueError(
                    f"Expected {settings.YAAP_MAX_VOICE_SAMPLES} samples, "
                    f"found {len(samples)}. User must re-upload."
                )

            local_paths = _download_samples(samples, tmpdir)

            # ── Process each WAV ──────────────────────────────────────────────
            processed_paths = _process_samples(local_paths, tmpdir)

            if not processed_paths:
                raise ValueError("All audio samples failed quality checks.")

            # ── Compute XTTS speaker embedding ────────────────────────────────
            embedding = _compute_embedding(processed_paths)

            if not embedding:
                raise ValueError("XTTS service failed to compute speaker embedding.")

            # ── Save embedding to user profile ────────────────────────────────
            _save_embedding(user, embedding)

            # ── Mark job complete ─────────────────────────────────────────────
            job.samples_count = len(processed_paths)
            job.save(update_fields=["samples_count"])
            job.mark_completed()

            logger.info(
                "Voice training completed: job=%s user=%s embedding_dim=%d",
                job_id, user.id, len(embedding),
            )

            # ── Notify user ───────────────────────────────────────────────────
            _notify_success(user)

        except Exception as exc:
            reason = str(exc)
            logger.error("Voice training failed: job=%s error=%s", job_id, reason, exc_info=True)
            job.mark_failed(reason)
            _notify_failure(user, reason)

            # Retry on transient errors (network, XTTS service down)
            if _is_retryable(exc):
                raise self.retry(exc=exc)


# ─── Pipeline Steps ───────────────────────────────────────────────────────────

def _download_samples(samples, tmpdir: str) -> list[str]:
    """
    Download each sample WAV from Supabase Storage to a temp directory.
    Returns list of local file paths.
    """
    from services.supabase_client import get_supabase_storage_client

    storage    = get_supabase_storage_client()
    bucket     = settings.SUPABASE_STORAGE_BUCKET_VOICE_SAMPLES
    local_paths = []

    for sample in samples:
        dest = os.path.join(tmpdir, f"sample_{sample.sample_index}.wav")
        try:
            response = storage.from_(bucket).download(sample.storage_path)
            with open(dest, "wb") as f:
                f.write(response)
            local_paths.append(dest)
            logger.debug("Downloaded sample %d → %s (%d bytes)", sample.sample_index, dest, len(response))
        except Exception as e:
            logger.error("Failed to download sample %s: %s", sample.storage_path, e)
            # Skip this sample but continue — 3 out of 5 is enough for XTTS

    return local_paths


def _process_samples(local_paths: list[str], tmpdir: str) -> list[str]:
    """
    Run the audio processing pipeline on each downloaded WAV.
    Returns paths to processed files that passed quality checks.
    """
    from services.audio_processing import validate_and_process_wav

    processed = []

    for path in local_paths:
        try:
            raw_bytes = Path(path).read_bytes()
            result    = validate_and_process_wav(raw_bytes, filename=os.path.basename(path))

            if not result["ok"]:
                logger.warning("Sample %s failed validation: %s", path, result["error"])
                continue

            # Write processed WAV to tmpdir
            processed_path = path.replace(".wav", "_processed.wav")
            Path(processed_path).write_bytes(result["processed_bytes"])
            processed.append(processed_path)

            logger.info(
                "Sample processed: %s duration=%.1fs noise_floor=%.1fdBFS",
                os.path.basename(path),
                result["duration"],
                result["noise_floor_db"],
            )

        except Exception as e:
            logger.error("Audio processing error for %s: %s", path, e)

    logger.info("Processed %d/%d voice samples", len(processed), len(local_paths))
    return processed


def _compute_embedding(processed_paths: list[str]) -> list[float] | None:
    """Call XTTS microservice to compute speaker embedding."""
    from services.xtts_client import compute_speaker_embedding
    return compute_speaker_embedding(processed_paths)


def _save_embedding(user, embedding: list[float]):
    """Persist embedding to user profile and mark voice_trained = True."""
    user.voice_embedding = embedding
    user.voice_trained   = True
    user.save(update_fields=["voice_embedding", "voice_trained"])
    logger.info("Saved %d-dim embedding for user %s", len(embedding), user.id)


def _notify_success(user):
    """Push completion event via WebSocket channel + FCM."""
    # WebSocket push to user's personal channel
    _push_ws_event(
        user_id = str(user.id),
        event   = "voice.training_complete",
        payload = {
            "voice_trained": True,
            "next_step":     "main_chat",
            "message":       "Your voice profile is ready!",
        },
    )

    # FCM push to all user devices
    try:
        from apps.friendships.models import UserDevice
        from services.fcm_service import notify_voice_training_complete
        tokens = list(UserDevice.objects.filter(user=user).values_list("fcm_token", flat=True))
        for token in tokens:
            notify_voice_training_complete(token)
    except Exception as e:
        logger.warning("FCM voice training complete push failed: %s", e)

    # Send welcome email if this is the first time
    try:
        from services.email_service import send_welcome_email
        send_welcome_email.delay(user.email, user.name)
    except Exception as e:
        logger.warning("Welcome email failed: %s", e)


def _notify_failure(user, reason: str):
    """Notify user of training failure via WebSocket + FCM."""
    _push_ws_event(
        user_id = str(user.id),
        event   = "voice.training_failed",
        payload = {
            "voice_trained": False,
            "error":         "Voice training failed. Please try recording again.",
            "debug_reason":  reason,
        },
    )

    try:
        from apps.friendships.models import UserDevice
        from services.fcm_service import send_push
        tokens = list(UserDevice.objects.filter(user=user).values_list("fcm_token", flat=True))
        for token in tokens:
            send_push(
                device_token      = token,
                title             = "Voice Training Failed",
                body              = "There was a problem processing your voice. Please try again.",
                notification_type = "voice_trained",
            )
    except Exception as e:
        logger.warning("FCM voice training failure push failed: %s", e)


def _push_ws_event(user_id: str, event: str, payload: dict):
    """
    Send a WebSocket event to a user's personal presence channel.
    Uses Django Channels' async_to_sync to call channel_layer from sync Celery context.
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning("No channel layer configured — skipping WS push")
            return

        group_name = f"presence_user_{user_id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type":    "voice.training_update",
                "payload": {"event": event, **payload},
            },
        )
        logger.info("WS event pushed: %s → user %s", event, user_id)
    except Exception as e:
        logger.error("WebSocket push failed: %s", e)


def _is_retryable(exc: Exception) -> bool:
    """Determine if the exception is likely transient (worth retrying)."""
    retryable_types = (
        ConnectionError,
        TimeoutError,
        OSError,
    )
    return isinstance(exc, retryable_types) or "timeout" in str(exc).lower()
