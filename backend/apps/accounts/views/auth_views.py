"""
YAAP Auth Views
All three authentication flows:
  1. Email + Password  (signup / login)
  2. Email OTP         (request code / verify code)
  3. Google OAuth      (verify ID token from Android SDK)
"""

import logging
import random
import string
from datetime import timedelta

import httpx
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.models import EmailOTP
from apps.accounts.serializers import (
    GoogleAuthSerializer,
    LoginSerializer,
    LogoutSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PasswordStrengthSerializer,
    SignupSerializer,
    UserMiniSerializer,
    _make_tokens,
)

  

from services.supabase_client import get_supabase_admin_client
from services.email_service import send_otp_email, send_password_reset_email

logger = logging.getLogger(__name__)
User = get_user_model()


def _success(data: dict, status_code=status.HTTP_200_OK) -> Response:
    return Response({"success": True, "data": data}, status=status_code)


# ─── Email + Password Signup ──────────────────────────────────────────────────

class SignupView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=SignupSerializer,
        responses={201: OpenApiResponse(description="User created, tokens returned")},
        summary="Register with email and password",
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        # Also register in Supabase Auth so Supabase RLS policies work
        try:
            supabase = get_supabase_admin_client()
            sb_user = supabase.auth.admin.create_user({
                "email": user.email,
                "password": request.data.get("password"),
                "email_confirm": True,
                "user_metadata": {"yaap_user_id": str(user.id)},
            })
            user.supabase_uid = sb_user.user.id
            user.is_verified  = True
            user.save(update_fields=["supabase_uid", "is_verified"])
        except Exception as e:
            logger.error("Supabase user creation failed for %s: %s", user.email, e)
            # Non-fatal — Django auth still works; Supabase sync can be retried

        tokens = _make_tokens(user)
        return _success(
            {
                "user":             UserMiniSerializer(user).data,
                "tokens":           tokens,
                "password_strength": serializer.validated_data.get("password_strength"),
                "next_step":        "personal_details",
            },
            status.HTTP_201_CREATED,
        )


# ─── Email + Password Login ───────────────────────────────────────────────────

class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=LoginSerializer,
        summary="Login with email and password",
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user   = serializer.validated_data["user"]
        tokens = _make_tokens(user)

        return _success({
            "user":      UserMiniSerializer(user).data,
            "tokens":    tokens,
            "next_step": _resolve_next_step(user),
        })


# ─── Email OTP — Request ──────────────────────────────────────────────────────

class OTPRequestView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=OTPRequestSerializer,
        summary="Request a 6-digit OTP for passwordless login",
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        # Invalidate all previous OTPs for this email
        EmailOTP.objects.filter(email=email, is_used=False).update(is_used=True)

        # Generate new OTP
        code = "".join(random.choices(string.digits, k=6))
        otp  = EmailOTP.objects.create(
            email      = email,
            code       = code,
            expires_at = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
        )

        # Send email (non-blocking via Celery)
        try:
            send_otp_email.delay(email, code)
        except Exception as e:
            logger.error("Failed to enqueue OTP email for %s: %s", email, e)
            # Fall back to synchronous send
            send_otp_email(email, code)

        return _success({
            "message":      f"A 6-digit code has been sent to {email}.",
            "expires_in":   settings.OTP_EXPIRY_MINUTES * 60,  # seconds
        })


# ─── Email OTP — Verify ───────────────────────────────────────────────────────

class OTPVerifyView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=OTPVerifySerializer,
        summary="Verify OTP code — creates account if new user",
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        otp   = serializer.validated_data["otp"]

        # Mark OTP as used
        otp.is_used = True
        otp.save(update_fields=["is_used"])

        # Get or create user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name":     email.split("@")[0],
                "auth_provider": User.AuthProvider.EMAIL_OTP,
                "is_verified":   True,
            },
        )
        if created:
            user.set_unusable_password()
            user.save()

            # Create in Supabase
            try:
                supabase = get_supabase_admin_client()
                sb_user  = supabase.auth.admin.create_user({
                    "email": email,
                    "email_confirm": True,
                    "user_metadata": {"yaap_user_id": str(user.id)},
                })
                user.supabase_uid = sb_user.user.id
                user.save(update_fields=["supabase_uid"])
            except Exception as e:
                logger.error("Supabase OTP user creation failed: %s", e)

        elif not user.is_verified:
            user.is_verified = True
            user.save(update_fields=["is_verified"])

        tokens = _make_tokens(user)
        return _success({
            "user":      UserMiniSerializer(user).data,
            "tokens":    tokens,
            "is_new":    created,
            "next_step": _resolve_next_step(user),
        })


# ─── Google OAuth ─────────────────────────────────────────────────────────────

class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=GoogleAuthSerializer,
        summary="Authenticate with Google ID token (from Android SDK)",
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_token = serializer.validated_data["id_token"]

        # Verify Google ID token
        google_payload = self._verify_google_token(id_token)
        if not google_payload:
            return Response(
                {"success": False, "error": {"code": "INVALID_TOKEN", "message": "Invalid Google ID token."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        email       = google_payload.get("email", "").lower().strip()
        full_name   = google_payload.get("name", "")
        avatar_url  = google_payload.get("picture", "")
        google_sub  = google_payload.get("sub", "")

        if not email:
            return Response(
                {"success": False, "error": {"code": "NO_EMAIL", "message": "Google account has no email."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name":     full_name,
                "display_name":  full_name,
                "avatar_url":    avatar_url,
                "auth_provider": User.AuthProvider.GOOGLE,
                "is_verified":   True,
            },
        )

        if created:
            try:
                supabase = get_supabase_admin_client()
                sb_user  = supabase.auth.admin.create_user({
                    "email": email,
                    "email_confirm": True,
                    "user_metadata": {
                        "yaap_user_id": str(user.id),
                        "google_sub":   google_sub,
                    },
                })
                user.supabase_uid = sb_user.user.id
                user.save(update_fields=["supabase_uid"])
            except Exception as e:
                logger.error("Supabase Google user creation failed: %s", e)
        else:
            # Update avatar if changed
            if avatar_url and user.avatar_url != avatar_url:
                user.avatar_url = avatar_url
                user.save(update_fields=["avatar_url"])

        tokens = _make_tokens(user)
        return _success({
            "user":      UserMiniSerializer(user).data,
            "tokens":    tokens,
            "is_new":    created,
            "next_step": _resolve_next_step(user),
        }, status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @staticmethod
    def _verify_google_token(id_token: str) -> dict | None:
        """Verify Google ID token via Google's tokeninfo endpoint."""
        try:
            response = httpx.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": id_token},
                timeout=5.0,
            )
            if response.status_code != 200:
                logger.warning("Google token verification failed: %s", response.text)
                return None

            payload = response.json()

            # Verify audience matches our client ID
            if payload.get("aud") != settings.GOOGLE_CLIENT_ID:
                logger.warning("Google token aud mismatch: %s", payload.get("aud"))
                return None

            return payload
        except Exception as e:
            logger.error("Google token verification error: %s", e)
            return None


# ─── Logout ───────────────────────────────────────────────────────────────────

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Logout", tags=["Authentication"])
    def post(self, request):
        refresh_token = request.data.get("refresh")

        # Try to blacklist refresh token only if client sent it.
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError as e:
                logger.warning("Logout with invalid refresh token: %s", e)
            except Exception as e:
                logger.warning("Unexpected logout blacklist error: %s", e)

        # Always try to mark user offline, but don't let this break logout.
        try:
            request.user.mark_offline()
        except Exception as e:
            logger.warning("Failed to mark user offline during logout: %s", e)

        return _success({"message": "Logged out successfully."})


# ─── Password Reset ───────────────────────────────────────────────────────────

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PasswordResetRequestSerializer, tags=["Authentication"])
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        # Always return 200 to avoid email enumeration
        if User.objects.filter(email=email, auth_provider=User.AuthProvider.EMAIL_PASSWORD).exists():
            try:
                send_password_reset_email.delay(email)
            except Exception:
                send_password_reset_email(email)

        return _success({
            "message": "If an account with that email exists, a password reset link has been sent."
        })


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PasswordResetConfirmSerializer, tags=["Authentication"])
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Supabase handles password reset token verification — we delegate
        try:
            supabase = get_supabase_admin_client()
            supabase.auth.admin.update_user_by_id(
                request.data.get("supabase_uid"),
                {"password": serializer.validated_data["new_password"]},
            )
        except Exception as e:
            logger.error("Password reset failed: %s", e)
            return Response(
                {"success": False, "error": {"code": "RESET_FAILED", "message": "Password reset failed."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _success({"message": "Password has been reset successfully."})


# ─── Password Strength Check ──────────────────────────────────────────────────

class PasswordStrengthView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PasswordStrengthSerializer, tags=["Authentication"])
    def post(self, request):
        serializer = PasswordStrengthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _success({"strength": serializer.validated_data["strength"]})


# ─── Token Refresh (custom wrapper) ──────────────────────────────────────────

class YAAPTokenRefreshView(TokenRefreshView):
    """Extends simplejwt's refresh with our success envelope."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            return Response({"success": True, "data": {"tokens": response.data}})
        return response


# ─── Helper ───────────────────────────────────────────────────────────────────

def _resolve_next_step(user: User) -> str:
    """
    Tells the Kotlin app which screen to navigate to after auth.
    The Android client uses this to skip already-completed onboarding steps.
    """
    if not user.profile_complete:
        return "personal_details"
    if not user.language_selected:
        return "language_selection"
    if not user.voice_trained:
        return "voice_training"
    return "main_chat"
