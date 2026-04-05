"""
YAAP Accounts Serializers
Covers all three auth methods: Email+Password, Email OTP, Google OAuth.
"""

import logging
import re
from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, EmailOTP

logger = logging.getLogger(__name__)

# ─── Password Strength ────────────────────────────────────────────────────────

def _password_strength(password: str) -> dict:
    """
    Returns strength info used by the frontend meter.
    Levels: weak | fair | strong | very_strong
    """
    score = 0
    has_upper   = bool(re.search(r"[A-Z]", password))
    has_lower   = bool(re.search(r"[a-z]", password))
    has_digit   = bool(re.search(r"\d", password))
    has_symbol  = bool(re.search(r"[^A-Za-z0-9]", password))
    length      = len(password)

    if length >= 8:  score += 1
    if length >= 12: score += 1
    if has_upper:    score += 1
    if has_lower:    score += 1
    if has_digit:    score += 1
    if has_symbol:   score += 1

    level = "weak"
    if score >= 6:   level = "very_strong"
    elif score >= 4: level = "strong"
    elif score >= 2: level = "fair"

    return {
        "score": score,
        "level": level,
        "has_upper": has_upper,
        "has_lower": has_lower,
        "has_digit": has_digit,
        "has_symbol": has_symbol,
        "length": length,
    }


# ─── JWT Custom Claims ────────────────────────────────────────────────────────

class YAAPTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds extra claims to JWT payload consumed by Kotlin client."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"]             = user.email
        token["display_name"]      = user.name
        token["language"]          = user.language_preference
        token["voice_trained"]     = user.voice_trained
        token["profile_complete"]  = user.profile_complete
        token["language_selected"] = user.language_selected
        token["avatar_url"]        = user.avatar_url
        return token


def _make_tokens(user: User) -> dict:
    """Utility: create access + refresh token pair for a user."""
    refresh = RefreshToken.for_user(user)
    # Add custom claims
    refresh["email"]             = user.email
    refresh["display_name"]      = user.name
    refresh["language"]          = user.language_preference
    refresh["voice_trained"]     = user.voice_trained
    refresh["profile_complete"]  = user.profile_complete
    refresh["language_selected"] = user.language_selected
    refresh["avatar_url"]        = user.avatar_url
    return {
        "access":  str(refresh.access_token),
        "refresh": str(refresh),
    }


# ─── Email + Password Signup ──────────────────────────────────────────────────

class SignupSerializer(serializers.Serializer):
    full_name        = serializers.CharField(min_length=2, max_length=150)
    email            = serializers.EmailField()
    password         = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    def validate_email(self, value):
        normalized = value.lower().strip()
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError(
                "An account with this email address already exists."
            )
        return normalized

    def validate_full_name(self, value):
        value = value.strip()
        if re.match(r"^\d+$", value):
            raise serializers.ValidationError("Name cannot be numeric only.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})

        strength = _password_strength(attrs["password"])
        if strength["level"] == "weak":
            raise serializers.ValidationError(
                {"password": "Password is too weak. Use at least 8 characters with mixed case and numbers."}
            )
        attrs["password_strength"] = strength
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        validated_data.pop("password_strength", None)
        password = validated_data.pop("password")
        email    = validated_data.pop("email")

        user = User.objects.create_user(
            email=email,
            password=password,
            auth_provider=User.AuthProvider.EMAIL_PASSWORD,
            **validated_data,
        )
        return user


class SignupResponseSerializer(serializers.Serializer):
    """Shape of the signup response returned to the Kotlin client."""
    user   = serializers.SerializerMethodField()
    tokens = serializers.SerializerMethodField()

    def get_user(self, obj):
        return UserMiniSerializer(obj).data

    def get_tokens(self, obj):
        return _make_tokens(obj)


# ─── Email + Password Login ───────────────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email    = attrs["email"].lower().strip()
        password = attrs["password"]

        user = authenticate(request=self.context.get("request"), username=email, password=password)
        if not user:
            raise serializers.ValidationError(
                {"non_field_errors": "Invalid credentials. Please check your email and password."}
            )
        if not user.is_active:
            raise serializers.ValidationError(
                {"non_field_errors": "Your account has been deactivated. Contact support."}
            )
        attrs["user"] = user
        return attrs

class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)

    def validate_refresh(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Refresh token is required.")
        return value.strip()

# ─── Email OTP ────────────────────────────────────────────────────────────────

class OTPRequestSerializer(serializers.Serializer):
    """Request a 6-digit OTP to the given email address."""
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class OTPVerifySerializer(serializers.Serializer):
    """Verify the OTP and return tokens."""
    email = serializers.EmailField()
    code  = serializers.CharField(min_length=6, max_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be a 6-digit number.")
        return value

    def validate(self, attrs):
        email = attrs["email"]
        code  = attrs["code"]

        try:
            otp = (
                EmailOTP.objects
                .filter(email=email, is_used=False)
                .order_by("-created_at")
                .first()
            )
            if not otp or not otp.is_valid():
                raise serializers.ValidationError(
                    {"code": "OTP has expired or is invalid. Please request a new one."}
                )
            if otp.code != code:
                otp.attempts += 1
                otp.save(update_fields=["attempts"])
                remaining = 5 - otp.attempts
                raise serializers.ValidationError(
                    {"code": f"Incorrect OTP. {remaining} attempt(s) remaining."}
                )
        except EmailOTP.DoesNotExist:
            raise serializers.ValidationError({"code": "No OTP found for this email."})

        attrs["otp"]   = otp
        attrs["email"] = email
        return attrs


# ─── Google OAuth ─────────────────────────────────────────────────────────────

class GoogleAuthSerializer(serializers.Serializer):
    """
    Receives the ID token from the Android Google Sign-In SDK.
    Backend verifies it with Google's tokeninfo endpoint.
    """
    id_token = serializers.CharField(write_only=True)


# ─── Token Refresh ────────────────────────────────────────────────────────────

class TokenRefreshResponseSerializer(serializers.Serializer):
    access  = serializers.CharField()
    refresh = serializers.CharField()


# ─── Password Reset ───────────────────────────────────────────────────────────

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token        = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        strength = _password_strength(value)
        if strength["level"] == "weak":
            raise serializers.ValidationError(
                "Password is too weak. Use at least 8 characters with uppercase, lowercase, and digits."
            )
        return value


# ─── Password Strength Check (standalone endpoint) ───────────────────────────

class PasswordStrengthSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        attrs["strength"] = _password_strength(attrs["password"])
        return attrs


# ─── User Profile ─────────────────────────────────────────────────────────────

class UserMiniSerializer(serializers.ModelSerializer):
    """Compact user representation used inside auth responses and friend lists."""

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "display_name", "avatar_url",
            "country_code", "timezone", "language_preference",
            "voice_trained", "profile_complete", "language_selected",
            "is_online", "last_seen", "auth_provider", "created_at",
        ]
        read_only_fields = fields


class UserProfileSerializer(serializers.ModelSerializer):
    """Full profile — returned for /api/v1/users/me/"""

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "display_name", "avatar_url",
            "bio", "date_of_birth", "country_code", "timezone",
            "language_preference", "voice_trained", "profile_complete",
            "language_selected", "is_online", "last_seen",
            "last_seen_visibility", "show_read_receipts", "show_online_status",
            "auth_provider", "is_verified", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "email", "supabase_uid", "auth_provider",
            "voice_trained", "is_verified", "created_at", "updated_at",
        ]

    def validate_display_name(self, value):
        value = value.strip()
        if len(value) < 2 or len(value) > 60:
            raise serializers.ValidationError("Display name must be 2–60 characters.")
        return value

    def validate_bio(self, value):
        if len(value) > 160:
            raise serializers.ValidationError("Bio cannot exceed 160 characters.")
        return value.strip()

    def validate_language_preference(self, value):
        if value not in settings.YAAP_SUPPORTED_LANGUAGES:
            raise serializers.ValidationError(
                f"Unsupported language. Choose from: {', '.join(settings.YAAP_SUPPORTED_LANGUAGES)}"
            )
        return value

    def validate_country_code(self, value):
        if value and len(value) != 2:
            raise serializers.ValidationError("Country code must be a 2-letter ISO code (e.g. 'PK').")
        return value.upper()


class UserPublicProfileSerializer(serializers.ModelSerializer):
    """
    Public profile — what OTHER users see.
    Respects privacy settings: last_seen and online status may be hidden.
    """
    last_seen   = serializers.SerializerMethodField()
    is_online   = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "display_name", "avatar_url", "bio",
            "country_code", "timezone", "language_preference",
            "is_online", "last_seen", "created_at",
        ]

    def get_last_seen(self, obj):
        requesting_user = self.context.get("request").user
        vis = obj.last_seen_visibility
        if vis == User.LastSeenVisibility.NOBODY:
            return None
        if vis == User.LastSeenVisibility.FRIENDS:
            from apps.friendships.models import Friendship
            if not Friendship.objects.are_friends(requesting_user, obj):
                return None
        return obj.last_seen

    def get_is_online(self, obj):
        if not obj.show_online_status:
            return None
        return obj.is_online


class UpdateLanguageSerializer(serializers.Serializer):
    language_preference = serializers.ChoiceField(
        choices=settings.YAAP_SUPPORTED_LANGUAGES
    )


class UserSearchSerializer(serializers.ModelSerializer):
    """Result card for /api/v1/users/search/"""
    friendship_status = serializers.SerializerMethodField()
    mutual_friends    = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "display_name", "avatar_url", "country_code",
            "language_preference", "is_online", "friendship_status", "mutual_friends",
        ]

    def get_friendship_status(self, obj):
        from apps.friendships.models import Friendship, FriendRequest
        requesting_user = self.context["request"].user
        if Friendship.objects.are_friends(requesting_user, obj):
            return "friends"
        req = FriendRequest.objects.filter(
            from_user=requesting_user, to_user=obj, status=FriendRequest.Status.PENDING
        ).first()
        if req:
            return "requested"
        return "none"

    def get_mutual_friends(self, obj):
        from apps.friendships.models import Friendship
        requesting_user = self.context["request"].user
        return Friendship.objects.mutual_friends_count(requesting_user, obj)
