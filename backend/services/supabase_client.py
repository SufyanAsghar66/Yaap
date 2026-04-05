"""
Supabase Client Service
Provides singleton-pattern clients for:
  - Admin client  (service role key — server only, never sent to clients)
  - Storage client (for avatar and voice sample uploads)

All Supabase interactions go through this module so credentials
are never scattered across the codebase.
"""

import logging
from functools import lru_cache
from django.conf import settings
from supabase import create_client, Client

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_supabase_admin_client() -> Client:
    """
    Returns a Supabase client authenticated with the SERVICE ROLE key.
    This client bypasses Row Level Security — use only server-side.
    The lru_cache ensures we reuse the same client instance (connection pooling).
    """
    client = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )
    logger.debug("Supabase admin client initialized.")
    return client


@lru_cache(maxsize=1)
def get_supabase_anon_client() -> Client:
    """
    Returns a Supabase client authenticated with the ANON key.
    Subject to Row Level Security — use for user-context operations.
    """
    client = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_ANON_KEY,
    )
    return client


def get_supabase_storage_client():
    """Returns the storage interface from the admin client."""
    return get_supabase_admin_client().storage


def get_signed_url(bucket: str, path: str, expires_in: int = 300) -> str:
    """
    Generate a signed URL for private file access.
    Default expiry: 300 seconds (5 minutes).
    """
    storage = get_supabase_storage_client()
    result  = storage.from_(bucket).create_signed_url(path, expires_in)
    return result.get("signedURL", "")


def upload_file(bucket: str, path: str, file_bytes: bytes, content_type: str = "application/octet-stream") -> str:
    """
    Upload bytes to Supabase Storage.
    Returns the public URL (for public buckets) or the storage path.
    """
    storage = get_supabase_storage_client()
    storage.from_(bucket).upload(
        path         = path,
        file         = file_bytes,
        file_options = {"content-type": content_type, "upsert": "true"},
    )
    public_url = storage.from_(bucket).get_public_url(path)
    return public_url


def delete_file(bucket: str, path: str) -> bool:
    """Delete a file from Supabase Storage. Returns True on success."""
    try:
        get_supabase_storage_client().from_(bucket).remove([path])
        return True
    except Exception as e:
        logger.error("Failed to delete %s/%s from Supabase Storage: %s", bucket, path, e)
        return False


def verify_supabase_jwt(token: str) -> dict | None:
    """
    Verify a Supabase-issued JWT and return the payload.
    Used by the WebSocket JWTAuthMiddleware to authenticate WS connections.
    """
    import jwt
    from django.conf import settings

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_ANON_KEY,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Supabase JWT expired.")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid Supabase JWT: %s", e)
        return None
