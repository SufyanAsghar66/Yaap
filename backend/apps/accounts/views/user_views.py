"""
YAAP User Profile Views
GET/PATCH own profile, avatar upload, language change, user search.
"""

import logging
from io import BytesIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from PIL import Image
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import (
    UpdateLanguageSerializer,
    UserProfileSerializer,
    UserPublicProfileSerializer,
    UserSearchSerializer,
)
from apps.friendships.models import Friendship
from services.supabase_client import get_supabase_storage_client

logger = logging.getLogger(__name__)
User = get_user_model()


def _ok(data, status_code=status.HTTP_200_OK):
    return Response({"success": True, "data": data}, status=status_code)


# ─── Own Profile ──────────────────────────────────────────────────────────────

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get own full profile", tags=["Profile"])
    def get(self, request):
        return _ok(UserProfileSerializer(request.user).data)

    @extend_schema(request=UserProfileSerializer, summary="Update own profile", tags=["Profile"])
    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Mark profile complete if required fields are present
        user = request.user
        if user.full_name and user.country_code and user.date_of_birth and not user.profile_complete:
            user.profile_complete = True
            user.save(update_fields=["profile_complete"])

        return _ok(UserProfileSerializer(user).data)


# ─── Avatar Upload ────────────────────────────────────────────────────────────

class AvatarUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    MAX_SIZE_BYTES = settings.YAAP_MAX_AVATAR_SIZE_MB * 1024 * 1024

    @extend_schema(summary="Upload or replace profile avatar", tags=["Profile"])
    def post(self, request):
        file = request.FILES.get("avatar")
        if not file:
            return Response(
                {"success": False, "error": {"code": "NO_FILE", "message": "No avatar file provided."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if file.size > self.MAX_SIZE_BYTES:
            return Response(
                {"success": False, "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": f"Avatar must be under {settings.YAAP_MAX_AVATAR_SIZE_MB} MB.",
                }},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_types = {"image/jpeg", "image/png", "image/webp"}
        if file.content_type not in allowed_types:
            return Response(
                {"success": False, "error": {"code": "INVALID_TYPE", "message": "Only JPEG, PNG, and WebP allowed."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Process: open → square crop → resize to 400×400 → JPEG
            img         = Image.open(file).convert("RGB")
            img         = _square_crop(img)
            img         = img.resize((400, 400), Image.LANCZOS)
            buffer      = BytesIO()
            img.save(buffer, format="JPEG", quality=85, optimize=True)
            buffer.seek(0)

            # Upload to Supabase Storage
            storage     = get_supabase_storage_client()
            path        = f"{request.user.id}/avatar.jpg"
            bucket      = settings.SUPABASE_STORAGE_BUCKET_AVATARS

            storage.from_(bucket).upload(
                path        = path,
                file        = buffer.read(),
                file_options = {"content-type": "image/jpeg", "upsert": "true"},
            )

            # Build public URL
            public_url  = storage.from_(bucket).get_public_url(path)

            request.user.avatar_url = public_url
            request.user.save(update_fields=["avatar_url"])

            return _ok({"avatar_url": public_url})

        except Exception as e:
            logger.error("Avatar upload failed for user %s: %s", request.user.id, e)
            return Response(
                {"success": False, "error": {"code": "UPLOAD_FAILED", "message": "Avatar upload failed."}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


def _square_crop(img: Image.Image) -> Image.Image:
    """Center-crop to a square."""
    w, h   = img.size
    side   = min(w, h)
    left   = (w - side) // 2
    top    = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


# ─── Language Preference ──────────────────────────────────────────────────────

class LanguagePreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=UpdateLanguageSerializer, summary="Update language preference", tags=["Profile"])
    def patch(self, request):
        serializer = UpdateLanguageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lang = serializer.validated_data["language_preference"]
        request.user.language_preference = lang
        request.user.language_selected   = True
        request.user.save(update_fields=["language_preference", "language_selected"])

        return _ok({
            "language_preference": lang,
            "language_name":       settings.YAAP_LANGUAGE_NAMES[lang],
        })


# ─── Public User Profile ──────────────────────────────────────────────────────

class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get another user's public profile", tags=["Profile"])
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": "User not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Blocked users return 404 to avoid enumeration
        from apps.friendships.models import Block
        if Block.objects.is_blocked(request.user, user):
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": "User not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = UserPublicProfileSerializer(user, context={"request": request})
        return _ok(serializer.data)


# ─── User Search ──────────────────────────────────────────────────────────────

class UserSearchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[OpenApiParameter("q", str, description="Search query (min 2 chars)")],
        summary="Search users by display name",
        tags=["Profile"],
    )
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response(
                {"success": False, "error": {"code": "QUERY_TOO_SHORT", "message": "Search query must be at least 2 characters."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Exclude self, inactive, and blocked users
        from apps.friendships.models import Block
        blocked_ids = Block.objects.blocked_user_ids(request.user)

        users = (
            User.objects
            .filter(
                Q(display_name__icontains=query) | Q(full_name__icontains=query),
                is_active=True,
            )
            .exclude(id=request.user.id)
            .exclude(id__in=blocked_ids)
            .select_related()
            [:30]
        )

        serializer = UserSearchSerializer(users, many=True, context={"request": request})
        return _ok({"results": serializer.data, "count": len(serializer.data)})


# ─── Supported Languages ──────────────────────────────────────────────────────

class SupportedLanguagesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List all XTTS-supported languages", tags=["Profile"])
    def get(self, request):
        languages = [
            {"code": code, "name": name}
            for code, name in settings.YAAP_LANGUAGE_NAMES.items()
        ]
        return _ok({"languages": languages})
