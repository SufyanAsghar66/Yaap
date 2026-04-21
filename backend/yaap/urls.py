"""YAAP URL Configuration"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    # ─── Admin ────────────────────────────────────────────────────────────────
    path("admin/", admin.site.urls),

    # ─── API v1 ───────────────────────────────────────────────────────────────
    path("api/v1/auth/",        include("apps.accounts.urls.auth_urls")),
    path("api/v1/users/",       include("apps.accounts.urls.user_urls")),
    path("api/v1/friends/",     include("apps.friendships.urls")),
    path("api/v1/conversations/", include("apps.messaging.urls")),
    path("api/v1/calls/",       include("apps.calls.urls")),
    path("api/v1/voice/",       include("apps.voice.urls")),

    # ─── API Docs (disable in production via SPECTACULAR_SETTINGS) ────────────
    path("api/schema/",         SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/",           SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/",          SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # ─── Health Check ─────────────────────────────────────────────────────────
    path("health/",             include("yaap.health")),
]
