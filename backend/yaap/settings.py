"""
YAAP Backend — Django Settings
Supports: Dev (DEBUG=True) and Production (DEBUG=False) via environment variables.
"""

import os
from datetime import timedelta
from pathlib import Path

import environ
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Environment ──────────────────────────────────────────────────────────────
env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    JWT_ACCESS_TOKEN_LIFETIME_MINUTES=(int, 15),
    JWT_REFRESH_TOKEN_LIFETIME_DAYS=(int, 30),
    OTP_EXPIRY_MINUTES=(int, 10),
)
environ.Env.read_env(BASE_DIR / ".env")

# ─── Core ─────────────────────────────────────────────────────────────────────
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = ["*"] if DEBUG else env("DJANGO_ALLOWED_HOSTS")

# ─── Applications ─────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "channels",
    "django_filters",
    "django_celery_results",
    "django_celery_beat",
    "drf_spectacular",
    "django_structlog",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.friendships",
    "apps.messaging",
    "apps.calls",
    "apps.voice",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── Middleware ───────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_structlog.middlewares.RequestMiddleware",
]

ROOT_URLCONF = "yaap.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ─── ASGI / WSGI ──────────────────────────────────────────────────────────────
WSGI_APPLICATION = "yaap.wsgi.application"
ASGI_APPLICATION = "yaap.asgi.application"

# ─── Database (Supabase PostgreSQL) ───────────────────────────────────────────
DATABASES = {
    "default": env.db("DATABASE_URL")
}
DATABASES["default"]["CONN_MAX_AGE"] = 60            # in cases where connection pooling isn't available, keep connections open for 1 minute to reduce overhead.
#DATABASES["default"]["CONN_MAX_AGE"] = 0            # disable persistent connections (use with connection pooling like PgBouncer or Supabase Pooling)

DATABASES["default"]["OPTIONS"] = {
    "connect_timeout": 10,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
}

# ─── Cache & Channel Layer (Redis) ────────────────────────────────────────────
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

#CACHES = {
#   "default": {
#        "BACKEND": "django.core.cache.backends.redis.RedisCache",
#        "LOCATION": REDIS_URL,
#        "OPTIONS": {
##            "CLIENT_CLASS": "django_redis.client.DefaultClient",
#      },
#        "KEY_PREFIX": "yaap",
#        "TIMEOUT": 300,
#    }
#}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        
        "KEY_PREFIX": "yaap",
        "TIMEOUT": 300,
    }
}


CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            "capacity": 1500,
            "expiry": 10,
        },
    },
}

# ─── Auth ─────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# ─── REST Framework ───────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "yaap.pagination.StandardResultsPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "yaap.exceptions.custom_exception_handler",
}

# ─── JWT ──────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("JWT_ACCESS_TOKEN_LIFETIME_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("JWT_REFRESH_TOKEN_LIFETIME_DAYS")),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_OBTAIN_SERIALIZER": "apps.accounts.serializers.YAAPTokenObtainPairSerializer",
}

# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Allow all origins in development (Android emulator/device)
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-device-id",
]

# ─── Celery ───────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_RESULT_EXPIRES = 3600
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # fair dispatch for long-running AI tasks

# ─── Supabase ─────────────────────────────────────────────────────────────────
SUPABASE_URL = env("SUPABASE_URL")
SUPABASE_ANON_KEY = env("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = env("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_STORAGE_BUCKET_AVATARS = env("SUPABASE_STORAGE_BUCKET_AVATARS", default="avatars")
SUPABASE_STORAGE_BUCKET_VOICE_SAMPLES = env("SUPABASE_STORAGE_BUCKET_VOICE_SAMPLES", default="voice-samples")

# ─── Google OAuth ─────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET")

# ─── Firebase ─────────────────────────────────────────────────────────────────
FIREBASE_CREDENTIALS_PATH = env("FIREBASE_CREDENTIALS_PATH", default="firebase-credentials.json")

# ─── DeepL ────────────────────────────────────────────────────────────────────
DEEPL_API_KEY = env("DEEPL_API_KEY", default="")

# ─── XTTS & Whisper Microservices ─────────────────────────────────────────────
XTTS_SERVICE_URL = env("XTTS_SERVICE_URL", default="http://localhost:8001")
WHISPER_SERVICE_URL = env("WHISPER_SERVICE_URL", default="http://localhost:8002")

# ─── OTP ──────────────────────────────────────────────────────────────────────
OTP_EXPIRY_MINUTES = env("OTP_EXPIRY_MINUTES")

# ─── Internationalization ─────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ─── Static Files ─────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ─── Default PK ───────────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Security (Production) ────────────────────────────────────────────────────
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = "DENY"

# ─── API Documentation ────────────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "YAAP API",
    "DESCRIPTION": "Real-time voice calling with AI language translation",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SECURITY": [{"BearerAuth": []}],
    "COMPONENT_SPLIT_REQUEST": True,
}

# ─── Rate Limiting ────────────────────────────────────────────────────────────
RATELIMIT_USE_CACHE = "default"
RATELIMIT_ENABLE = True

import os

SENTRY_DSN = os.getenv("SENTRY_DSN")

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=1.0,
        send_default_pii=True,
    )
# ─── Logging ──────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "structlog.stdlib.ProcessorFormatter",
            "processor": "structlog.processors.JSONRenderer",
        },
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if not DEBUG else "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "apps": {"handlers": ["console"], "level": "DEBUG" if DEBUG else "INFO", "propagate": False},
        "services": {"handlers": ["console"], "level": "DEBUG" if DEBUG else "INFO", "propagate": False},
    },
}

# ─── YAAP App Config ──────────────────────────────────────────────────────────
YAAP_SUPPORTED_LANGUAGES = [
    "en", "es", "fr", "de", "it", "pt", "pl", "tr",
    "ru", "nl", "cs", "ar", "zh", "ja", "ko", "hu", "hi",
]

YAAP_LANGUAGE_NAMES = {
    "en": "English",      "es": "Spanish",   "fr": "French",
    "de": "German",       "it": "Italian",   "pt": "Portuguese",
    "pl": "Polish",       "tr": "Turkish",   "ru": "Russian",
    "nl": "Dutch",        "cs": "Czech",     "ar": "Arabic",
    "zh": "Chinese",      "ja": "Japanese",  "ko": "Korean",
    "hu": "Hungarian",    "hi": "Hindi",
}

YAAP_MAX_VOICE_SAMPLES = 5
YAAP_MAX_AVATAR_SIZE_MB = 5
YAAP_FRIEND_REQUEST_COOLDOWN_DAYS = 7
YAAP_MESSAGE_DELETE_WINDOW_HOURS = 48

# ─── coturn TURN Server ───────────────────────────────────────────────────────
COTURN_HOST   = env("COTURN_HOST",   default="turn.yaap.app")
COTURN_PORT   = env("COTURN_PORT",   default=3478)
COTURN_SECRET = env("COTURN_SECRET", default="yaap-turn-secret-change-in-production")

# ─── Celery Beat Schedule ─────────────────────────────────────────────────────
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Clean up stale calls every 5 minutes
    "cleanup-stale-calls": {
        "task":     "calls.cleanup_stale_calls",
        "schedule": 300,   # every 5 minutes
    },
    # Expire old OTPs every hour
    "cleanup-expired-otps": {
        "task":     "email.cleanup_expired_otps",
        "schedule": crontab(minute=0),
    },
}
