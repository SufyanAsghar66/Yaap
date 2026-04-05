"""
YAAP Custom User Model
Extends AbstractBaseUser for full control over the auth flow.
UUIDs are used as primary keys throughout for security and Supabase compatibility.
"""

import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.conf import settings
from django.utils import timezone as tz
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email address is required.")
        email = self.normalize_email(email)
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Central user entity.
    Auth is handled via Supabase (tokens validated server-side),
    but Django keeps its own user record for relational queries.
    """

    class AuthProvider(models.TextChoices):
        EMAIL_PASSWORD = "email_password", "Email & Password"
        EMAIL_OTP     = "email_otp",      "Email OTP"
        GOOGLE        = "google",          "Google"

    # ─── Identity ─────────────────────────────────────────────────────────────
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email          = models.EmailField(unique=True, db_index=True)
    full_name      = models.CharField(max_length=150)
    display_name   = models.CharField(max_length=60, blank=True)
    supabase_uid   = models.CharField(max_length=36, unique=True, blank=True, null=True,
                                       help_text="Supabase Auth UID — used to verify JWT sub claim")

    # ─── Profile ──────────────────────────────────────────────────────────────
    avatar_url     = models.TextField(blank=True, default="")
    bio            = models.CharField(max_length=160, blank=True, default="")
    date_of_birth  = models.DateField(null=True, blank=True)
    country_code   = models.CharField(max_length=2, blank=True, default="")
    timezone = models.CharField(max_length=64, blank=True, default="UTC")


    # ─── Language & Voice ─────────────────────────────────────────────────────
    language_preference = models.CharField(
        max_length=5,
        choices=[(code, name) for code, name in settings.YAAP_LANGUAGE_NAMES.items()],
        default="en",
    )
    voice_trained       = models.BooleanField(default=False)
    voice_embedding     = models.JSONField(null=True, blank=True,
                                           help_text="XTTS speaker embedding vector (256-dim list)")

    # ─── Auth Provider ────────────────────────────────────────────────────────
    auth_provider  = models.CharField(
        max_length=20,
        choices=AuthProvider.choices,
        default=AuthProvider.EMAIL_PASSWORD,
    )

    # ─── Onboarding State ─────────────────────────────────────────────────────
    profile_complete     = models.BooleanField(default=False)
    language_selected    = models.BooleanField(default=False)

    # ─── Presence ─────────────────────────────────────────────────────────────
    is_online    = models.BooleanField(default=False, db_index=True)
    last_seen    = models.DateTimeField(null=True, blank=True, db_index=True)

    # ─── Privacy Settings ─────────────────────────────────────────────────────
    class LastSeenVisibility(models.TextChoices):
        EVERYONE = "everyone", "Everyone"
        FRIENDS  = "friends",  "Friends Only"
        NOBODY   = "nobody",   "Nobody"

    last_seen_visibility   = models.CharField(max_length=10, choices=LastSeenVisibility.choices, default=LastSeenVisibility.EVERYONE)
    show_read_receipts     = models.BooleanField(default=True)
    show_online_status     = models.BooleanField(default=True)

    # ─── Django Admin Fields ──────────────────────────────────────────────────
    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False,
                                       help_text="Email verified (OTP or Supabase callback)")
    created_at  = models.DateTimeField(default=tz.now)
    updated_at  = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["display_name"]),
            models.Index(fields=["supabase_uid"]),
            models.Index(fields=["is_online", "last_seen"]),
        ]

    def __str__(self):
        return f"{self.display_name or self.full_name} <{self.email}>"

    @property
    def name(self) -> str:
        return self.display_name or self.full_name

    def mark_online(self):
        self.is_online = True
        self.save(update_fields=["is_online"])

    def mark_offline(self):
        self.is_online = False
        self.last_seen = timezone.now()
        self.save(update_fields=["is_online", "last_seen"])


class EmailOTP(models.Model):
    """
    Stores time-limited one-time passwords for passwordless email login.
    OTPs are 6-digit codes, valid for OTP_EXPIRY_MINUTES.
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email      = models.EmailField(db_index=True)
    code       = models.CharField(max_length=6)
    is_used    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts   = models.PositiveSmallIntegerField(default=0,
                                                   help_text="Number of failed verification attempts")

    class Meta:
        db_table = "email_otps"
        indexes = [models.Index(fields=["email", "is_used", "expires_at"])]

    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() < self.expires_at and self.attempts < 5

    def __str__(self):
        return f"OTP for {self.email} ({'used' if self.is_used else 'active'})"
