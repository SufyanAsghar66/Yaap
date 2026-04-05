"""
YAAP Health Check
Extended in Phase 7 to include XTTS and Whisper microservice status.
Used by AWS ALB / GCP load balancer and monitoring.
"""
from django.http import JsonResponse
from django.urls import path
from django.db import connection
from django.core.cache import cache


def health_check(request):
    health = {"status": "ok", "checks": {}}

    # ── Database ──────────────────────────────────────────────────────────────
    try:
        connection.ensure_connection()
        health["checks"]["database"] = "ok"
    except Exception as e:
        health["checks"]["database"] = f"error: {e}"
        health["status"] = "degraded"

    # ── Redis ─────────────────────────────────────────────────────────────────
    try:
        cache.set("health_ping", "pong", timeout=5)
        assert cache.get("health_ping") == "pong"
        health["checks"]["redis"] = "ok"
    except Exception as e:
        health["checks"]["redis"] = f"error: {e}"
        health["status"] = "degraded"

    status_code = 200 if health["status"] == "ok" else 503
    return JsonResponse(health, status=status_code)


def deep_health_check(request):
    """
    Extended health: also checks XTTS and Whisper microservices.
    Called by monitoring systems, not load balancer (slower).
    """
    health = {"status": "ok", "checks": {}}

    # Database
    try:
        connection.ensure_connection()
        health["checks"]["database"] = "ok"
    except Exception as e:
        health["checks"]["database"] = f"error: {e}"
        health["status"] = "degraded"

    # Redis
    try:
        cache.set("health_ping", "pong", timeout=5)
        assert cache.get("health_ping") == "pong"
        health["checks"]["redis"] = "ok"
    except Exception as e:
        health["checks"]["redis"] = f"error: {e}"
        health["status"] = "degraded"

    # XTTS microservice
    try:
        from services.xtts_client import is_xtts_service_healthy
        if is_xtts_service_healthy():
            health["checks"]["xtts_service"] = "ok"
        else:
            health["checks"]["xtts_service"] = "unreachable"
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["xtts_service"] = f"error: {e}"
        health["status"] = "degraded"

    # Whisper microservice
    try:
        from services.whisper_service import is_whisper_service_healthy
        if is_whisper_service_healthy():
            health["checks"]["whisper_service"] = "ok"
        else:
            health["checks"]["whisper_service"] = "unreachable"
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["whisper_service"] = f"error: {e}"
        health["status"] = "degraded"

    status_code = 200 if health["status"] == "ok" else 503
    return JsonResponse(health, status=status_code)


urlpatterns = [
    path("",       health_check,      name="health-check"),
    path("deep/",  deep_health_check, name="health-deep"),
]
