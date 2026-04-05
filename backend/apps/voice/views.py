"""
Voice App Views
"""
import logging
from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import VoiceSample, VoiceSentence, VoiceTrainingJob
from .serializers import (
    VoiceSampleSerializer, VoiceSampleUploadSerializer,
    VoiceSentenceSerializer, VoiceTrainingJobSerializer,
)

logger = logging.getLogger(__name__)
def _ok(d, sc=status.HTTP_200_OK): return Response({"success": True, "data": d}, status=sc)
def _err(c, m, sc=status.HTTP_400_BAD_REQUEST): return Response({"success": False, "error": {"code": c, "message": m}}, status=sc)


class VoiceSentencesView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        lang = request.user.language_preference
        qs   = VoiceSentence.objects.for_language(lang)
        if not qs.exists():
            lang = "en"
            qs   = VoiceSentence.objects.for_language(lang)
        if not qs.exists():
            return _err("NO_SENTENCES", "Training sentences not found.", status.HTTP_503_SERVICE_UNAVAILABLE)
        return _ok({"language": lang, "language_name": settings.YAAP_LANGUAGE_NAMES.get(lang, lang),
                    "sentences": VoiceSentenceSerializer(qs, many=True).data, "total_required": settings.YAAP_MAX_VOICE_SAMPLES})


class VoiceSampleUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    def post(self, request):
        s = VoiceSampleUploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        audio_file   = s.validated_data["audio_file"]
        sample_index = s.validated_data["sample_index"]
        sentence_id  = s.validated_data.get("sentence_id")
        from services.audio_processing import validate_and_process_wav
        raw_bytes = audio_file.read()
        result    = validate_and_process_wav(raw_bytes, filename=audio_file.name)
        if not result["ok"]:
            return _err("INVALID_AUDIO", result["error"])
        storage_path = f"{request.user.id}/sample_{sample_index}.wav"
        try:
            from services.supabase_client import upload_file
            upload_file(settings.SUPABASE_STORAGE_BUCKET_VOICE_SAMPLES, storage_path, result["processed_bytes"], "audio/wav")
        except Exception as e:
            logger.error("Upload failed: %s", e)
            return _err("UPLOAD_FAILED", "Storage error.", status.HTTP_500_INTERNAL_SERVER_ERROR)
        sentence = None
        if sentence_id:
            try: sentence = VoiceSentence.objects.get(id=sentence_id)
            except VoiceSentence.DoesNotExist: pass
        sample, created = VoiceSample.objects.update_or_create(
            user=request.user, sample_index=sample_index,
            defaults={"storage_path": storage_path, "sentence": sentence,
                      "duration_seconds": result["duration"], "file_size_bytes": len(result["processed_bytes"]),
                      "noise_floor_db": result["noise_floor_db"]},
        )
        uploaded_count = VoiceSample.objects.filter(user=request.user).count()
        return _ok({"sample": VoiceSampleSerializer(sample).data, "samples_uploaded": uploaded_count,
                    "samples_required": settings.YAAP_MAX_VOICE_SAMPLES,
                    "all_uploaded": uploaded_count >= settings.YAAP_MAX_VOICE_SAMPLES,
                    "noise_warning": result["noise_floor_db"] > -40.0,
                    "noise_floor_db": result["noise_floor_db"]},
                   status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class VoiceSampleDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    def delete(self, request, sample_index):
        if not (1 <= sample_index <= settings.YAAP_MAX_VOICE_SAMPLES):
            return _err("INVALID_INDEX", f"sample_index must be 1-{settings.YAAP_MAX_VOICE_SAMPLES}.")
        try:
            sample = VoiceSample.objects.get(user=request.user, sample_index=sample_index)
        except VoiceSample.DoesNotExist:
            return _err("NOT_FOUND", "Sample not found.", status.HTTP_404_NOT_FOUND)
        try:
            from services.supabase_client import delete_file
            delete_file(settings.SUPABASE_STORAGE_BUCKET_VOICE_SAMPLES, sample.storage_path)
        except Exception as e:
            logger.warning("Storage delete failed: %s", e)
        sample.delete()
        return _ok({"message": f"Sample {sample_index} deleted."})


class VoiceTrainView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        user           = request.user
        uploaded_count = VoiceSample.objects.filter(user=user).count()
        if uploaded_count < settings.YAAP_MAX_VOICE_SAMPLES:
            return _err("INSUFFICIENT_SAMPLES",
                        f"Upload all {settings.YAAP_MAX_VOICE_SAMPLES} samples first. Uploaded: {uploaded_count}.")
        running = VoiceTrainingJob.objects.filter(
            user=user, status__in=[VoiceTrainingJob.Status.PENDING, VoiceTrainingJob.Status.PROCESSING]
        ).first()
        if running:
            return _ok({"job": VoiceTrainingJobSerializer(running).data, "message": "Training already in progress."})
        with transaction.atomic():
            job = VoiceTrainingJob.objects.create(user=user, samples_count=uploaded_count)
        from tasks.voice_tasks import train_voice_model
        task = train_voice_model.apply_async(args=[str(job.id)], queue="voice_training")
        job.celery_task_id = task.id
        job.save(update_fields=["celery_task_id"])
        logger.info("Voice training job: job=%s user=%s task=%s", job.id, user.id, task.id)
        return _ok({"job": VoiceTrainingJobSerializer(job).data, "message": "Training started."}, status.HTTP_202_ACCEPTED)


class VoiceStatusView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user       = request.user
        samples    = VoiceSample.objects.filter(user=user).select_related("sentence").order_by("sample_index")
        active_job = VoiceTrainingJob.objects.filter(user=user).order_by("-created_at").first()
        uploaded   = samples.count()
        return _ok({"voice_trained": user.voice_trained, "samples_uploaded": uploaded,
                    "samples_required": settings.YAAP_MAX_VOICE_SAMPLES,
                    "all_samples_uploaded": uploaded >= settings.YAAP_MAX_VOICE_SAMPLES,
                    "active_job": VoiceTrainingJobSerializer(active_job).data if active_job else None,
                    "samples": VoiceSampleSerializer(samples, many=True).data})


class VoiceResetView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        user    = request.user
        samples = VoiceSample.objects.filter(user=user)
        from services.supabase_client import delete_file
        for s in samples:
            try: delete_file(settings.SUPABASE_STORAGE_BUCKET_VOICE_SAMPLES, s.storage_path)
            except Exception as e: logger.warning("Storage delete failed: %s", e)
        with transaction.atomic():
            samples.delete()
            VoiceTrainingJob.objects.filter(
                user=user, status__in=[VoiceTrainingJob.Status.PENDING, VoiceTrainingJob.Status.PROCESSING]
            ).update(status=VoiceTrainingJob.Status.FAILED, error_message="Reset by user.")
            user.voice_trained   = False
            user.voice_embedding = None
            user.save(update_fields=["voice_trained", "voice_embedding"])
        return _ok({"message": "Voice profile reset. Please re-record."})
