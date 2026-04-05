"""
Voice App Models
VoiceSentence  — bank of 5 sentences per language shown during training
VoiceSample    — individual recorded audio upload (5 per user)
VoiceTrainingJob — Celery job record tracking XTTS embedding computation
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class VoiceSentenceManager(models.Manager):
    def for_language(self, language_code: str):
        """Return all 5 sentences for a language, ordered by position."""
        return (
            self.filter(language=language_code)
            .order_by("position")
        )


class VoiceSentence(models.Model):
    """
    Bank of training sentences.
    Seeded via supabase_schema.sql and the management command load_voice_sentences.
    5 sentences per each of the 17 supported languages = 85 rows total.
    """
    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    language = models.CharField(max_length=5, db_index=True)
    sentence = models.TextField()
    position = models.PositiveSmallIntegerField(
        help_text="Display order 1–5 on the training screen"
    )
    objects  = VoiceSentenceManager()

    class Meta:
        db_table        = "voice_sentences"
        unique_together = [("language", "position")]
        ordering        = ["language", "position"]

    def __str__(self):
        return f"[{self.language}:{self.position}] {self.sentence[:60]}"


class VoiceSample(models.Model):
    """
    One recorded audio clip uploaded by a user during voice training.
    Each user must upload exactly 5 samples (one per sentence).
    Audio is stored in Supabase Storage (private bucket).
    """
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user             = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="voice_samples",
    )
    sentence         = models.ForeignKey(
        VoiceSentence, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="samples",
    )
    sample_index     = models.PositiveSmallIntegerField(
        help_text="Which of the 5 samples this is (1–5)"
    )
    storage_path     = models.TextField(
        help_text="Supabase Storage path: voice-samples/{user_id}/sample_{n}.wav"
    )
    storage_url      = models.TextField(
        blank=True, default="",
        help_text="Signed URL (refreshed on demand — not stored permanently)"
    )
    duration_seconds = models.FloatField(null=True, blank=True)
    file_size_bytes  = models.PositiveIntegerField(null=True, blank=True)
    sample_rate      = models.PositiveIntegerField(
        default=16000,
        help_text="Expected 16000 Hz (16 kHz mono WAV)"
    )
    noise_floor_db   = models.FloatField(
        null=True, blank=True,
        help_text="Ambient noise floor measured during upload validation"
    )
    uploaded_at      = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table        = "voice_samples"
        unique_together = [("user", "sample_index")]
        indexes         = [models.Index(fields=["user", "sample_index"])]

    def __str__(self):
        return f"VoiceSample({self.user_id}, index={self.sample_index})"


class VoiceTrainingJob(models.Model):
    """
    Tracks the Celery background task that computes the XTTS speaker embedding.
    One job per training attempt. A user can re-train by submitting new samples
    (old samples are replaced; a new job is created).
    """

    class Status(models.TextChoices):
        PENDING    = "pending",    "Pending — waiting for Celery worker"
        PROCESSING = "processing", "Processing — downloading samples and computing embedding"
        COMPLETED  = "completed",  "Completed — embedding saved to user profile"
        FAILED     = "failed",     "Failed — see error_message"

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user           = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="voice_training_jobs",
    )
    status         = models.CharField(
        max_length=12, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    celery_task_id = models.CharField(
        max_length=64, blank=True, default="",
        help_text="Celery AsyncResult task ID for status polling"
    )
    error_message  = models.TextField(blank=True, default="")
    samples_count  = models.PositiveSmallIntegerField(default=0)
    started_at     = models.DateTimeField(null=True, blank=True)
    completed_at   = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "voice_training_jobs"
        indexes  = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["celery_task_id"]),
        ]

    def __str__(self):
        return f"VoiceTrainingJob({self.user_id}, {self.status})"

    def mark_processing(self, celery_task_id: str):
        self.status         = self.Status.PROCESSING
        self.celery_task_id = celery_task_id
        self.started_at     = timezone.now()
        self.save(update_fields=["status", "celery_task_id", "started_at"])

    def mark_completed(self):
        self.status       = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])

    def mark_failed(self, reason: str):
        self.status        = self.Status.FAILED
        self.error_message = reason
        self.completed_at  = timezone.now()
        self.save(update_fields=["status", "error_message", "completed_at"])

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
