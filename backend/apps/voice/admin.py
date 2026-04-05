from django.contrib import admin
from .models import VoiceSentence, VoiceSample, VoiceTrainingJob

@admin.register(VoiceSentence)
class VoiceSentenceAdmin(admin.ModelAdmin):
    list_display  = ["language", "position", "sentence"]
    list_filter   = ["language"]
    ordering      = ["language", "position"]

@admin.register(VoiceSample)
class VoiceSampleAdmin(admin.ModelAdmin):
    list_display  = ["user", "sample_index", "duration_seconds", "noise_floor_db", "uploaded_at"]
    list_filter   = ["sample_index"]
    search_fields = ["user__email"]

@admin.register(VoiceTrainingJob)
class VoiceTrainingJobAdmin(admin.ModelAdmin):
    list_display   = ["user", "status", "samples_count", "created_at", "completed_at"]
    list_filter    = ["status"]
    search_fields  = ["user__email", "celery_task_id"]
    readonly_fields = ["id", "celery_task_id", "created_at", "started_at", "completed_at"]
