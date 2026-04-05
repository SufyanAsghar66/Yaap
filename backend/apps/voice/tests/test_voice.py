"""
Voice app tests — Phase 4
Covers: sentence fetch, sample upload validation, training trigger,
status polling, re-record delete, reset.
"""

import io
import struct
import wave
import pytest
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from unittest.mock import MagicMock, patch

from apps.voice.models import VoiceSample, VoiceSentence, VoiceTrainingJob


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_wav_bytes(duration_secs: float = 4.0, sample_rate: int = 16000) -> bytes:
    """Generate a minimal valid WAV file with a sine-like signal."""
    import math
    num_samples = int(duration_secs * sample_rate)
    samples     = [int(8000 * math.sin(2 * math.pi * 440 * i / sample_rate)) for i in range(num_samples)]
    buf         = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{num_samples}h", *samples))
    return buf.getvalue()


@pytest.fixture
def sentences(db):
    """Seed 5 English sentences."""
    objs = []
    for i in range(1, 6):
        objs.append(VoiceSentence.objects.create(
            language = "en",
            sentence = f"Test sentence number {i} for voice training.",
            position = i,
        ))
    return objs


@pytest.fixture
def voice_wav():
    return _make_wav_bytes(duration_secs=4.0)


# ─── Sentences ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestVoiceSentences:

    URL = "/api/v1/voice/sentences/"

    def test_returns_5_sentences(self, auth_client, sentences):
        client, user = auth_client
        user.language_preference = "en"
        user.save()
        resp = client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["language"] == "en"
        assert len(data["sentences"]) == 5
        assert data["total_required"] == 5

    def test_sentences_ordered_by_position(self, auth_client, sentences):
        client, _ = auth_client
        resp      = client.get(self.URL)
        positions = [s["position"] for s in resp.json()["data"]["sentences"]]
        assert positions == sorted(positions)

    def test_falls_back_to_english_if_no_sentences(self, auth_client, db):
        client, user = auth_client
        user.language_preference = "ko"  # no Korean sentences seeded
        user.save()
        # Seed English fallback
        for i in range(1, 6):
            VoiceSentence.objects.create(language="en", sentence=f"Sentence {i}", position=i)
        resp = client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["data"]["language"] == "en"

    def test_requires_authentication(self, api_client):
        resp = api_client.get(self.URL)
        assert resp.status_code == 401


# ─── Sample Upload ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestVoiceSampleUpload:

    URL = "/api/v1/voice/samples/"

    @patch("services.audio_processing.validate_and_process_wav")
    @patch("services.supabase_client.upload_file")
    def test_upload_success(self, mock_upload, mock_validate, auth_client, voice_wav, sentences):
        mock_validate.return_value = {
            "ok": True, "processed_bytes": voice_wav,
            "duration": 4.0, "noise_floor_db": -50.0, "error": None,
        }
        mock_upload.return_value = "https://storage.example.com/sample.wav"

        client, user = auth_client
        audio        = io.BytesIO(voice_wav)
        audio.name   = "sample.wav"

        resp = client.post(self.URL, {
            "audio_file":   audio,
            "sample_index": 1,
            "sentence_id":  str(sentences[0].id),
        }, format="multipart")

        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["sample"]["sample_index"] == 1
        assert data["samples_uploaded"] == 1
        assert data["all_uploaded"] is False
        assert VoiceSample.objects.filter(user=user, sample_index=1).exists()

    @patch("services.audio_processing.validate_and_process_wav")
    def test_upload_too_short_rejected(self, mock_validate, auth_client, voice_wav):
        mock_validate.return_value = {
            "ok": False, "processed_bytes": None,
            "duration": 1.0, "noise_floor_db": -60.0,
            "error": "Recording too short (1.0s). Minimum is 3.0s.",
        }
        client, _ = auth_client
        audio     = io.BytesIO(voice_wav)
        audio.name = "short.wav"
        resp = client.post(self.URL, {"audio_file": audio, "sample_index": 1}, format="multipart")
        assert resp.status_code == 400
        assert "INVALID_AUDIO" in resp.json()["error"]["code"]

    def test_invalid_sample_index_rejected(self, auth_client, voice_wav):
        client, _ = auth_client
        audio     = io.BytesIO(voice_wav)
        audio.name = "audio.wav"
        resp = client.post(self.URL, {"audio_file": audio, "sample_index": 99}, format="multipart")
        assert resp.status_code == 400

    @patch("services.audio_processing.validate_and_process_wav")
    @patch("services.supabase_client.upload_file")
    def test_upsert_existing_sample(self, mock_upload, mock_validate, auth_client, voice_wav, sentences):
        """Re-uploading sample_index=1 should update the existing record."""
        mock_validate.return_value = {"ok": True, "processed_bytes": voice_wav, "duration": 4.0, "noise_floor_db": -55.0, "error": None}
        mock_upload.return_value = "https://storage/new.wav"
        client, user = auth_client

        # Upload once
        audio = io.BytesIO(voice_wav); audio.name = "a.wav"
        client.post(self.URL, {"audio_file": audio, "sample_index": 2}, format="multipart")

        # Upload again (re-record)
        audio2 = io.BytesIO(voice_wav); audio2.name = "b.wav"
        resp   = client.post(self.URL, {"audio_file": audio2, "sample_index": 2}, format="multipart")
        assert resp.status_code == 200   # 200 because update_or_create returned existing
        assert VoiceSample.objects.filter(user=user, sample_index=2).count() == 1

    @patch("services.audio_processing.validate_and_process_wav")
    @patch("services.supabase_client.upload_file")
    def test_all_uploaded_flag(self, mock_upload, mock_validate, auth_client, voice_wav):
        mock_validate.return_value = {"ok": True, "processed_bytes": voice_wav, "duration": 4.0, "noise_floor_db": -55.0, "error": None}
        mock_upload.return_value = "https://storage/x.wav"
        client, user = auth_client

        for i in range(1, 6):
            audio = io.BytesIO(voice_wav); audio.name = f"s{i}.wav"
            resp  = client.post(self.URL, {"audio_file": audio, "sample_index": i}, format="multipart")

        assert resp.json()["data"]["all_uploaded"] is True
        assert resp.json()["data"]["samples_uploaded"] == 5


# ─── Training Trigger ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestVoiceTrain:

    URL = "/api/v1/voice/train/"

    def _upload_5_samples(self, user):
        for i in range(1, 6):
            VoiceSample.objects.create(
                user=user, sample_index=i,
                storage_path=f"{user.id}/sample_{i}.wav",
                duration_seconds=4.0,
            )

    @patch("tasks.voice_tasks.train_voice_model.apply_async")
    def test_train_creates_job_and_dispatches_celery(self, mock_apply, auth_client):
        mock_apply.return_value = MagicMock(id="celery-task-abc")
        client, user = auth_client
        self._upload_5_samples(user)

        resp = client.post(self.URL)
        assert resp.status_code == 202
        data = resp.json()["data"]
        assert data["job"]["status"] == "pending"
        assert VoiceTrainingJob.objects.filter(user=user).exists()
        mock_apply.assert_called_once()

    def test_train_requires_5_samples(self, auth_client):
        client, user = auth_client
        # Only 3 samples
        for i in range(1, 4):
            VoiceSample.objects.create(user=user, sample_index=i, storage_path=f"{user.id}/s{i}.wav", duration_seconds=4.0)
        resp = client.post(self.URL)
        assert resp.status_code == 400
        assert "INSUFFICIENT_SAMPLES" in resp.json()["error"]["code"]

    @patch("tasks.voice_tasks.train_voice_model.apply_async")
    def test_train_does_not_duplicate_running_job(self, mock_apply, auth_client):
        mock_apply.return_value = MagicMock(id="t1")
        client, user = auth_client
        self._upload_5_samples(user)
        VoiceTrainingJob.objects.create(user=user, status=VoiceTrainingJob.Status.PROCESSING)

        resp = client.post(self.URL)
        assert resp.status_code == 200           # 200, not 202
        mock_apply.assert_not_called()           # no new Celery task
        assert VoiceTrainingJob.objects.filter(user=user).count() == 1


# ─── Status Polling ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestVoiceStatus:

    URL = "/api/v1/voice/status/"

    def test_status_no_samples(self, auth_client):
        client, user = auth_client
        resp = client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["voice_trained"] is False
        assert data["samples_uploaded"] == 0
        assert data["all_samples_uploaded"] is False
        assert data["active_job"] is None

    def test_status_with_completed_job(self, auth_client):
        client, user = auth_client
        for i in range(1, 6):
            VoiceSample.objects.create(user=user, sample_index=i, storage_path=f"x/s{i}.wav", duration_seconds=4.0)
        job = VoiceTrainingJob.objects.create(user=user, status=VoiceTrainingJob.Status.COMPLETED, samples_count=5)
        job.mark_completed()
        user.voice_trained = True
        user.save()

        resp = client.get(self.URL)
        data = resp.json()["data"]
        assert data["voice_trained"] is True
        assert data["samples_uploaded"] == 5
        assert data["active_job"]["status"] == "completed"
        assert data["active_job"]["progress_percent"] == 100
        assert len(data["samples"]) == 5


# ─── Reset Voice Profile ──────────────────────────────────────────────────────

@pytest.mark.django_db
class TestVoiceReset:

    URL = "/api/v1/voice/reset/"

    @patch("services.supabase_client.delete_file")
    def test_reset_clears_samples_and_resets_flags(self, mock_delete, auth_client):
        client, user = auth_client
        for i in range(1, 6):
            VoiceSample.objects.create(user=user, sample_index=i, storage_path=f"x/s{i}.wav", duration_seconds=4.0)
        user.voice_trained   = True
        user.voice_embedding = [0.1] * 256
        user.save()

        resp = client.post(self.URL)
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.voice_trained is False
        assert user.voice_embedding is None
        assert VoiceSample.objects.filter(user=user).count() == 0
        assert mock_delete.call_count == 5   # one delete per sample

    @patch("services.supabase_client.delete_file")
    def test_reset_cancels_running_job(self, mock_delete, auth_client):
        client, user = auth_client
        job = VoiceTrainingJob.objects.create(user=user, status=VoiceTrainingJob.Status.PROCESSING)
        client.post(self.URL)
        job.refresh_from_db()
        assert job.status == VoiceTrainingJob.Status.FAILED


# ─── Sample Delete (Re-record) ────────────────────────────────────────────────

@pytest.mark.django_db
class TestSampleDelete:

    @patch("services.supabase_client.delete_file")
    def test_delete_specific_sample(self, mock_delete, auth_client):
        client, user = auth_client
        VoiceSample.objects.create(user=user, sample_index=3, storage_path=f"{user.id}/sample_3.wav", duration_seconds=4.0)
        resp = client.delete("/api/v1/voice/samples/3/")
        assert resp.status_code == 200
        assert not VoiceSample.objects.filter(user=user, sample_index=3).exists()
        mock_delete.assert_called_once()

    def test_delete_nonexistent_sample_404(self, auth_client):
        client, _ = auth_client
        resp = client.delete("/api/v1/voice/samples/2/")
        assert resp.status_code == 404

    def test_delete_invalid_index(self, auth_client):
        client, _ = auth_client
        resp = client.delete("/api/v1/voice/samples/99/")
        assert resp.status_code == 400
