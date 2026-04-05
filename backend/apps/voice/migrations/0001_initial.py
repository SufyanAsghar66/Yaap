"""voice — Initial migration (UUID PKs)"""
import uuid
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="VoiceSentence",
            fields=[
                ("id",       models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("language", models.CharField(db_index=True, max_length=5)),
                ("sentence", models.TextField()),
                ("position", models.PositiveSmallIntegerField()),
            ],
            options={"db_table": "voice_sentences", "ordering": ["language", "position"]},
        ),
        migrations.CreateModel(
            name="VoiceSample",
            fields=[
                ("id",               models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("user",             models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="voice_samples",   to=settings.AUTH_USER_MODEL)),
                ("sentence",         models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="samples", to="voice.voicesentence")),
                ("sample_index",     models.PositiveSmallIntegerField()),
                ("storage_path",     models.TextField()),
                ("storage_url",      models.TextField(blank=True, default="")),
                ("duration_seconds", models.FloatField(blank=True, null=True)),
                ("file_size_bytes",  models.PositiveIntegerField(blank=True, null=True)),
                ("sample_rate",      models.PositiveIntegerField(default=16000)),
                ("noise_floor_db",   models.FloatField(blank=True, null=True)),
                ("uploaded_at",      models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"db_table": "voice_samples"},
        ),
        migrations.CreateModel(
            name="VoiceTrainingJob",
            fields=[
                ("id",             models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("user",           models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="voice_training_jobs", to=settings.AUTH_USER_MODEL)),
                ("status",         models.CharField(choices=[("pending","Pending"),("processing","Processing"),("completed","Completed"),("failed","Failed")], db_index=True, default="pending", max_length=12)),
                ("celery_task_id", models.CharField(blank=True, default="", max_length=64)),
                ("error_message",  models.TextField(blank=True, default="")),
                ("samples_count",  models.PositiveSmallIntegerField(default=0)),
                ("started_at",     models.DateTimeField(blank=True, null=True)),
                ("completed_at",   models.DateTimeField(blank=True, null=True)),
                ("created_at",     models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "voice_training_jobs"},
        ),
        migrations.AlterUniqueTogether(name="voicesentence", unique_together={("language", "position")}),
        migrations.AlterUniqueTogether(name="voicesample",   unique_together={("user", "sample_index")}),
        migrations.AddIndex(model_name="voicesample",      index=models.Index(fields=["user", "sample_index"], name="vsample_user_idx")),
        migrations.AddIndex(model_name="voicetrainingjob", index=models.Index(fields=["user", "status"],       name="vjob_user_status_idx")),
        migrations.AddIndex(model_name="voicetrainingjob", index=models.Index(fields=["celery_task_id"],       name="vjob_celery_idx")),
    ]
