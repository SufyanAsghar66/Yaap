"""
YAAP Test Settings
Overrides production settings for fast, dependency-free local testing.
  - SQLite in-memory DB  (no Supabase/PostgreSQL needed)
  - Dummy cache          (no Redis needed)
  - InMemory channel layer (no Redis needed)
  - All external services mocked via environment flags
  - Celery runs eagerly  (tasks execute synchronously, no broker needed)

Usage:
  DJANGO_SETTINGS_MODULE=yaap.settings_test pytest
"""

from yaap.settings import *   # noqa: F401,F403 — import everything then override

# ─── Database — SQLite in memory ─────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME":   ":memory:",
    }
}

# ─── Cache — local memory, no Redis ──────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ─── Channel layer — in-memory, no Redis ─────────────────────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# ─── Celery — eager (synchronous) execution ───────────────────────────────────
CELERY_TASK_ALWAYS_EAGER        = True
CELERY_TASK_EAGER_PROPAGATES    = True

# ─── Passwords — fastest hasher ───────────────────────────────────────────────
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ─── Email — capture in memory ────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# ─── Disable Sentry ───────────────────────────────────────────────────────────
SENTRY_DSN = ""

# ─── Fake external service URLs ───────────────────────────────────────────────
XTTS_SERVICE_URL    = "http://localhost:8001"
WHISPER_SERVICE_URL = "http://localhost:8002"

# ─── Supabase — fake keys (service is mocked in tests) ───────────────────────
SUPABASE_URL              = "https://fake.supabase.co"
SUPABASE_ANON_KEY         = "fake-anon-key"
SUPABASE_SERVICE_ROLE_KEY = "fake-service-role-key"

# ─── Google OAuth ─────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = "fake-google-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "fake-secret"

# ─── Firebase ─────────────────────────────────────────────────────────────────
FIREBASE_CREDENTIALS_PATH = "/tmp/fake-firebase.json"

# ─── JWT — short lifetime for tests ──────────────────────────────────────────
from datetime import timedelta
SIMPLE_JWT = {
    **SIMPLE_JWT,  # noqa: F405
    "ACCESS_TOKEN_LIFETIME":  timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

# ─── DeepL ────────────────────────────────────────────────────────────────────
DEEPL_API_KEY = "fake-deepl-key"

# ─── coturn ───────────────────────────────────────────────────────────────────
COTURN_HOST   = "localhost"
COTURN_PORT   = 3478
COTURN_SECRET = "test-secret"

# ─── Silence migration warnings ───────────────────────────────────────────────
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="django")

# ─── Logging — quiet during tests ─────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"], "level": "CRITICAL"},
}
