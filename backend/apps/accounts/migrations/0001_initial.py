"""accounts — Initial migration (UUID PKs throughout)"""
import uuid
import django.utils.timezone
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [('auth', '0012_alter_user_first_name_max_length'),]
    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("id",                   models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("password",             models.CharField(max_length=128, verbose_name="password")),
                ("last_login",           models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser",         models.BooleanField(default=False)),
                ("email",                models.EmailField(db_index=True, max_length=254, unique=True)),
                ("full_name",            models.CharField(max_length=150)),
                ("display_name",         models.CharField(blank=True, max_length=60)),
                ("supabase_uid",         models.CharField(blank=True, max_length=36, null=True, unique=True)),
                ("avatar_url",           models.TextField(blank=True, default="")),
                ("bio",                  models.CharField(blank=True, default="", max_length=160)),
                ("date_of_birth",        models.DateField(blank=True, null=True)),
                ("country_code",         models.CharField(blank=True, default="", max_length=2)),
                ("timezone",             models.CharField(blank=True, default="UTC", max_length=64)),
                ("language_preference",  models.CharField(default="en", max_length=5)),
                ("voice_trained",        models.BooleanField(default=False)),
                ("voice_embedding",      models.JSONField(blank=True, null=True)),
                ("auth_provider",        models.CharField(choices=[("email_password","Email & Password"),("email_otp","Email OTP"),("google","Google")], default="email_password", max_length=20)),
                ("profile_complete",     models.BooleanField(default=False)),
                ("language_selected",    models.BooleanField(default=False)),
                ("is_online",            models.BooleanField(db_index=True, default=False)),
                ("last_seen",            models.DateTimeField(blank=True, db_index=True, null=True)),
                ("last_seen_visibility", models.CharField(choices=[("everyone","Everyone"),("friends","Friends Only"),("nobody","Nobody")], default="everyone", max_length=10)),
                ("show_read_receipts",   models.BooleanField(default=True)),
                ("show_online_status",   models.BooleanField(default=True)),
                ("is_active",            models.BooleanField(default=True)),
                ("is_staff",             models.BooleanField(default=False)),
                ("is_verified",          models.BooleanField(default=False)),
                ("created_at",           models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at",           models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "users"},
        ),
        migrations.CreateModel(
            name="EmailOTP",
            fields=[
                ("id",         models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("email",      models.EmailField(db_index=True, max_length=254)),
                ("code",       models.CharField(max_length=6)),
                ("is_used",    models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("attempts",   models.PositiveSmallIntegerField(default=0)),
            ],
            options={"db_table": "email_otps"},
        ),
        migrations.AddField(
            model_name="user",
            name="groups",
            field=models.ManyToManyField(blank=True, related_name="user_set", related_query_name="user", to="auth.group", verbose_name="groups"),
        ),
        migrations.AddField(
            model_name="user",
            name="user_permissions",
            field=models.ManyToManyField(blank=True, related_name="user_set", related_query_name="user", to="auth.permission", verbose_name="user permissions"),
        ),
        migrations.AddIndex(model_name="user", index=models.Index(fields=["email"], name="users_email_idx")),
        migrations.AddIndex(model_name="user", index=models.Index(fields=["display_name"], name="users_display_name_idx")),
        migrations.AddIndex(model_name="user", index=models.Index(fields=["supabase_uid"], name="users_supabase_uid_idx")),
        migrations.AddIndex(model_name="user", index=models.Index(fields=["is_online", "last_seen"], name="users_presence_idx")),
        migrations.AddIndex(model_name="emailotp", index=models.Index(fields=["email", "is_used", "expires_at"], name="emailotp_lookup_idx")),
    ]
