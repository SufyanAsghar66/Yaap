"""
Auth endpoint tests — Phase 1.
Covers: signup, login, OTP request/verify, logout, password strength, token refresh.
"""

import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

from apps.accounts.models import EmailOTP

User = get_user_model()


# ─── Signup ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSignup:

    URL = "/api/v1/auth/signup/"

    def test_signup_success(self, api_client, mocker):
        mocker.patch("apps.accounts.views.auth_views.get_supabase_admin_client")
        resp = api_client.post(self.URL, {
            "full_name":        "Alice Yaap",
            "email":            "alice@yaap.app",
            "password":         "SecurePass1!",
            "password_confirm": "SecurePass1!",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert "access" in data["data"]["tokens"]
        assert "refresh" in data["data"]["tokens"]
        assert data["data"]["next_step"] == "personal_details"
        assert User.objects.filter(email="alice@yaap.app").exists()

    def test_signup_duplicate_email(self, api_client, user, mocker):
        mocker.patch("apps.accounts.views.auth_views.get_supabase_admin_client")
        resp = api_client.post(self.URL, {
            "full_name":        "Dupe User",
            "email":            user.email,
            "password":         "SecurePass1!",
            "password_confirm": "SecurePass1!",
        })
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    def test_signup_password_mismatch(self, api_client):
        resp = api_client.post(self.URL, {
            "full_name":        "Bob",
            "email":            "bob@yaap.app",
            "password":         "SecurePass1!",
            "password_confirm": "DifferentPass1!",
        })
        assert resp.status_code == 400

    def test_signup_weak_password_rejected(self, api_client):
        resp = api_client.post(self.URL, {
            "full_name":        "Weak Bob",
            "email":            "weak@yaap.app",
            "password":         "abc",
            "password_confirm": "abc",
        })
        assert resp.status_code == 400

    def test_signup_numeric_name_rejected(self, api_client):
        resp = api_client.post(self.URL, {
            "full_name":        "12345",
            "email":            "numeric@yaap.app",
            "password":         "SecurePass1!",
            "password_confirm": "SecurePass1!",
        })
        assert resp.status_code == 400


# ─── Login ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLogin:

    URL = "/api/v1/auth/login/"

    def test_login_success(self, api_client, user):
        resp = api_client.post(self.URL, {"email": user.email, "password": "TestPass123!"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "access" in data["data"]["tokens"]

    def test_login_wrong_password(self, api_client, user):
        resp = api_client.post(self.URL, {"email": user.email, "password": "WrongPass!"})
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    def test_login_nonexistent_email(self, api_client):
        resp = api_client.post(self.URL, {"email": "ghost@yaap.app", "password": "Pass123!"})
        assert resp.status_code == 400

    def test_login_returns_next_step(self, api_client, user):
        resp = api_client.post(self.URL, {"email": user.email, "password": "TestPass123!"})
        assert "next_step" in resp.json()["data"]

    def test_login_inactive_user_rejected(self, api_client, user):
        user.is_active = False
        user.save()
        resp = api_client.post(self.URL, {"email": user.email, "password": "TestPass123!"})
        assert resp.status_code == 400


# ─── OTP ──────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestOTP:

    REQUEST_URL = "/api/v1/auth/otp/request/"
    VERIFY_URL  = "/api/v1/auth/otp/verify/"

    def test_otp_request_success(self, api_client, mocker):
        mocker.patch("apps.accounts.views.auth_views.send_otp_email.delay")
        resp = api_client.post(self.REQUEST_URL, {"email": "otp_user@yaap.app"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert EmailOTP.objects.filter(email="otp_user@yaap.app").exists()

    def test_otp_verify_success(self, api_client, mocker):
        mocker.patch("apps.accounts.views.auth_views.get_supabase_admin_client")
        email = "verify@yaap.app"
        otp   = EmailOTP.objects.create(
            email      = email,
            code       = "123456",
            expires_at = timezone.now() + timedelta(minutes=10),
        )
        resp = api_client.post(self.VERIFY_URL, {"email": email, "code": "123456"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "access" in data["data"]["tokens"]
        assert data["data"]["is_new"] is True
        otp.refresh_from_db()
        assert otp.is_used is True

    def test_otp_verify_wrong_code(self, api_client):
        email = "wrong@yaap.app"
        EmailOTP.objects.create(
            email      = email,
            code       = "111111",
            expires_at = timezone.now() + timedelta(minutes=10),
        )
        resp = api_client.post(self.VERIFY_URL, {"email": email, "code": "999999"})
        assert resp.status_code == 400

    def test_otp_verify_expired(self, api_client):
        email = "expired@yaap.app"
        EmailOTP.objects.create(
            email      = email,
            code       = "222222",
            expires_at = timezone.now() - timedelta(minutes=1),  # already expired
        )
        resp = api_client.post(self.VERIFY_URL, {"email": email, "code": "222222"})
        assert resp.status_code == 400

    def test_otp_invalidated_on_new_request(self, api_client, mocker):
        mocker.patch("apps.accounts.views.auth_views.send_otp_email.delay")
        email = "invalidate@yaap.app"
        old   = EmailOTP.objects.create(
            email      = email,
            code       = "000000",
            expires_at = timezone.now() + timedelta(minutes=10),
        )
        api_client.post(self.REQUEST_URL, {"email": email})
        old.refresh_from_db()
        assert old.is_used is True  # old OTP invalidated


# ─── Password Strength ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPasswordStrength:

    URL = "/api/v1/auth/password/strength/"

    @pytest.mark.parametrize("password,expected_level", [
        ("abc",            "weak"),
        ("abcdefgh",       "fair"),
        ("Abcdefgh1",      "strong"),
        ("Abcdefgh1!xyz",  "very_strong"),
    ])
    def test_strength_levels(self, api_client, password, expected_level):
        resp = api_client.post(self.URL, {"password": password})
        assert resp.status_code == 200
        assert resp.json()["data"]["strength"]["level"] == expected_level


# ─── Logout ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLogout:

    URL = "/api/v1/auth/logout/"

    def test_logout_success(self, auth_client):
        client, user = auth_client
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = str(RefreshToken.for_user(user))
        resp    = client.post(self.URL, {"refresh": refresh})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_logout_requires_auth(self, api_client):
        resp = api_client.post(self.URL, {"refresh": "fake"})
        assert resp.status_code == 401

    def test_logout_missing_refresh_token(self, auth_client):
        client, _ = auth_client
        resp      = client.post(self.URL, {})
        assert resp.status_code == 400
