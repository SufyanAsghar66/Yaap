"""friendships — Initial migration (UUID PKs)"""
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
            name="FriendRequest",
            fields=[
                ("id",           models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("from_user",    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sent_friend_requests", to=settings.AUTH_USER_MODEL)),
                ("to_user",      models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="received_friend_requests", to=settings.AUTH_USER_MODEL)),
                ("status",       models.CharField(choices=[("pending","Pending"),("accepted","Accepted"),("declined","Declined"),("cancelled","Cancelled")], db_index=True, default="pending", max_length=10)),
                ("message",      models.CharField(blank=True, default="", max_length=200)),
                ("created_at",   models.DateTimeField(auto_now_add=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"db_table": "friend_requests"},
        ),
        migrations.CreateModel(
            name="Friendship",
            fields=[
                ("id",         models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("user_a",     models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="friendships_as_a", to=settings.AUTH_USER_MODEL)),
                ("user_b",     models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="friendships_as_b", to=settings.AUTH_USER_MODEL)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "friendships"},
        ),
        migrations.CreateModel(
            name="Block",
            fields=[
                ("id",         models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("blocker",    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blocks_made",     to=settings.AUTH_USER_MODEL)),
                ("blocked",    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blocks_received", to=settings.AUTH_USER_MODEL)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "blocks"},
        ),
        migrations.CreateModel(
            name="UserDevice",
            fields=[
                ("id",           models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("user",         models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="devices", to=settings.AUTH_USER_MODEL)),
                ("fcm_token",    models.TextField(unique=True)),
                ("device_name",  models.CharField(blank=True, default="", max_length=100)),
                ("created_at",   models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "user_devices"},
        ),
        migrations.AlterUniqueTogether(name="friendrequest", unique_together={("from_user", "to_user", "status")}),
        migrations.AlterUniqueTogether(name="friendship",    unique_together={("user_a", "user_b")}),
        migrations.AlterUniqueTogether(name="block",         unique_together={("blocker", "blocked")}),
        migrations.AddIndex(model_name="friendrequest", index=models.Index(fields=["to_user",   "status"], name="freq_to_user_status_idx")),
        migrations.AddIndex(model_name="friendrequest", index=models.Index(fields=["from_user", "status"], name="freq_from_user_status_idx")),
        migrations.AddIndex(model_name="friendship",    index=models.Index(fields=["user_a"],              name="friendship_user_a_idx")),
        migrations.AddIndex(model_name="friendship",    index=models.Index(fields=["user_b"],              name="friendship_user_b_idx")),
        migrations.AddIndex(model_name="userdevice",    index=models.Index(fields=["user"],                name="userdevice_user_idx")),
    ]
