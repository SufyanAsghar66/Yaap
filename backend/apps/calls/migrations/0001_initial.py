"""calls — Initial migration (UUID PKs)"""
import uuid
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
            name="CallRoom",
            fields=[
                ("id",               models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("room_id",          models.UUIDField(unique=True, default=uuid.uuid4, editable=False)),
                ("caller",           models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outgoing_calls", to=settings.AUTH_USER_MODEL)),
                ("callee",           models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="incoming_calls", to=settings.AUTH_USER_MODEL)),
                ("status",           models.CharField(choices=[("initiated","Initiated"),("answered","Answered"),("missed","Missed"),("declined","Declined"),("ended","Ended")], db_index=True, default="initiated", max_length=10)),
                ("started_at",       models.DateTimeField(auto_now_add=True)),
                ("answered_at",      models.DateTimeField(blank=True, null=True)),
                ("ended_at",         models.DateTimeField(blank=True, null=True)),
                ("duration_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("caller_language",  models.CharField(default="en", max_length=5)),
                ("callee_language",  models.CharField(default="en", max_length=5)),
            ],
            options={"db_table": "call_rooms"},
        ),
        migrations.CreateModel(
            name="IceCredential",
            fields=[
                ("id",         models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("room",       models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="ice_credential", to="calls.callroom")),
                ("username",   models.CharField(max_length=128)),
                ("credential", models.CharField(max_length=256)),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "ice_credentials"},
        ),
        migrations.AddIndex(model_name="callroom", index=models.Index(fields=["caller", "-started_at"], name="call_caller_idx")),
        migrations.AddIndex(model_name="callroom", index=models.Index(fields=["callee", "-started_at"], name="call_callee_idx")),
        migrations.AddIndex(model_name="callroom", index=models.Index(fields=["status"],                name="call_status_idx")),
        migrations.AddIndex(model_name="callroom", index=models.Index(fields=["room_id"],               name="call_room_id_idx")),
    ]
