"""messaging — Initial migration (UUID PKs)"""
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
            name="Conversation",
            fields=[
                ("id",            models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("participant_a", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversations_as_a", to=settings.AUTH_USER_MODEL)),
                ("participant_b", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversations_as_b", to=settings.AUTH_USER_MODEL)),
                ("created_at",    models.DateTimeField(auto_now_add=True)),
                ("updated_at",    models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "conversations"},
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id",                   models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("conversation",         models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages",      to="messaging.conversation")),
                ("sender",               models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sent_messages", to=settings.AUTH_USER_MODEL)),
                ("content",              models.TextField()),
                ("original_language",    models.CharField(default="en", max_length=5)),
                ("status",               models.CharField(choices=[("sent","Sent"),("delivered","Delivered"),("read","Read")], db_index=True, default="sent", max_length=10)),
                ("deleted_for_everyone", models.BooleanField(db_index=True, default=False)),
                ("deleted_at",           models.DateTimeField(blank=True, null=True)),
                ("created_at",           models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at",           models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "messages"},
        ),
        migrations.AddField(
            model_name="conversation",
            name="last_message",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="messaging.message"),
        ),
        migrations.CreateModel(
            name="MessageDeletion",
            fields=[
                ("message",    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deletions", to="messaging.message")),
                ("user",       models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("deleted_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "message_deletions"},
        ),
        migrations.CreateModel(
            name="MessageTranslation",
            fields=[
                ("id",                 models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("message",            models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="translations", to="messaging.message")),
                ("language",           models.CharField(max_length=5)),
                ("translated_content", models.TextField()),
                ("created_at",         models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "message_translations"},
        ),
        migrations.AlterUniqueTogether(name="conversation",       unique_together={("participant_a", "participant_b")}),
        migrations.AlterUniqueTogether(name="messagedeletion",    unique_together={("message", "user")}),
        migrations.AlterUniqueTogether(name="messagetranslation", unique_together={("message", "language")}),
        migrations.AddIndex(model_name="message",      index=models.Index(fields=["conversation", "-created_at"], name="msg_conv_time_idx")),
        migrations.AddIndex(model_name="conversation", index=models.Index(fields=["-updated_at"],                 name="conv_updated_idx")),
    ]
