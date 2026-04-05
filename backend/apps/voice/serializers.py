"""Voice App Serializers"""

from django.conf import settings
from rest_framework import serializers
from .models import VoiceSample, VoiceTrainingJob, VoiceSentence


class VoiceSentenceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = VoiceSentence
        fields = ["id", "language", "sentence", "position"]
        read_only_fields = fields


class VoiceSampleUploadSerializer(serializers.Serializer):
    """Validates an incoming voice sample upload."""
    audio_file   = serializers.FileField()
    sample_index = serializers.IntegerField(min_value=1, max_value=settings.YAAP_MAX_VOICE_SAMPLES)
    sentence_id  = serializers.UUIDField(required=False, allow_null=True)

    def validate_audio_file(self, value):
        allowed_types = {"audio/wav", "audio/wave", "audio/x-wav", "audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg"}
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Unsupported audio format '{value.content_type}'. Upload WAV, WebM, OGG, or MP4."
            )
        max_bytes = 50 * 1024 * 1024  # 50 MB
        if value.size > max_bytes:
            raise serializers.ValidationError("Audio file exceeds 50 MB limit.")
        return value


class VoiceSampleSerializer(serializers.ModelSerializer):
    sentence = VoiceSentenceSerializer(read_only=True)

    class Meta:
        model  = VoiceSample
        fields = ["id", "sample_index", "sentence", "duration_seconds",
                  "file_size_bytes", "noise_floor_db", "uploaded_at"]
        read_only_fields = fields


class VoiceTrainingJobSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()

    class Meta:
        model  = VoiceTrainingJob
        fields = ["id", "status", "samples_count", "error_message",
                  "started_at", "completed_at", "created_at",
                  "duration_seconds", "progress_percent"]
        read_only_fields = fields

    def get_duration_seconds(self, obj):
        return obj.duration_seconds

    def get_progress_percent(self, obj):
        mapping = {
            VoiceTrainingJob.Status.PENDING:    10,
            VoiceTrainingJob.Status.PROCESSING: 50,
            VoiceTrainingJob.Status.COMPLETED:  100,
            VoiceTrainingJob.Status.FAILED:     0,
        }
        return mapping.get(obj.status, 0)


class VoiceStatusSerializer(serializers.Serializer):
    """Full training status response returned to the Kotlin app."""
    voice_trained        = serializers.BooleanField()
    samples_uploaded     = serializers.IntegerField()
    samples_required     = serializers.IntegerField()
    all_samples_uploaded = serializers.BooleanField()
    active_job           = VoiceTrainingJobSerializer(allow_null=True)
    samples              = VoiceSampleSerializer(many=True)
