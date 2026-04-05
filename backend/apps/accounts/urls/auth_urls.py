from django.urls import path
from apps.accounts.views.auth_views import (
    SignupView,
    LoginView,
    OTPRequestView,
    OTPVerifyView,
    GoogleAuthView,
    LogoutView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    PasswordStrengthView,
    YAAPTokenRefreshView,
)

urlpatterns = [
    # Email + Password
    path("signup/",                  SignupView.as_view(),               name="auth-signup"),
    path("login/",                   LoginView.as_view(),                name="auth-login"),

    # Email OTP (passwordless)
    path("otp/request/",             OTPRequestView.as_view(),           name="auth-otp-request"),
    path("otp/verify/",              OTPVerifyView.as_view(),            name="auth-otp-verify"),

    # Google OAuth
    path("google/",                  GoogleAuthView.as_view(),           name="auth-google"),

    # Session management
    path("logout/",                  LogoutView.as_view(),               name="auth-logout"),
    path("token/refresh/",           YAAPTokenRefreshView.as_view(),     name="auth-token-refresh"),

    # Password
    path("password/reset/",          PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("password/reset/confirm/",  PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("password/strength/",       PasswordStrengthView.as_view(),     name="auth-password-strength"),
]
