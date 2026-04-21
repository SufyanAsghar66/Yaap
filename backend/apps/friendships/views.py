"""
Friendships Views
All endpoints for friend requests, friends list, block/unblock, and FCM device registration.

Endpoint map (all under /api/v1/friends/):
  GET    /                          — list accepted friends
  DELETE /{friendship_id}/          — unfriend

  POST   /request/                  — send a friend request
  GET    /requests/received/        — incoming pending requests
  GET    /requests/sent/            — outgoing pending requests
  POST   /requests/{id}/accept/     — accept an incoming request
  POST   /requests/{id}/decline/    — decline an incoming request
  DELETE /requests/{id}/            — cancel an outgoing request

  POST   /block/                    — block a user
  DELETE /block/{user_id}/          — unblock a user
  GET    /blocked/                  — list blocked users

  POST   /devices/                  — register FCM device token
  DELETE /devices/{token}/          — remove FCM token on logout
"""

import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from services.fcm_service import notify_friend_request
from .models import Block, FriendRequest, Friendship, UserDevice
from .serializers import (
    BlockSerializer,
    BlockUserSerializer,
    FriendRequestMiniSerializer,
    FriendRequestSerializer,
    FriendSerializer,
    RegisterDeviceSerializer,
    SendFriendRequestSerializer,
)

logger = logging.getLogger(__name__)
User   = get_user_model()


def _ok(data, status_code=status.HTTP_200_OK):
    return Response({"success": True, "data": data}, status=status_code)


def _err(code, message, status_code=status.HTTP_400_BAD_REQUEST):
    return Response(
        {"success": False, "error": {"code": code, "message": message}},
        status=status_code,
    )


# ─── Friends List & Unfriend ──────────────────────────────────────────────────

    
class FriendsListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List all accepted friends", tags=["Friendships"])
    def get(self, request):
        qs = Friendship.objects.filter(
            Q(user_a=request.user) | Q(user_b=request.user)
        ).select_related("user_a", "user_b")

        serializer = FriendSerializer(qs, many=True, context={"request": request})
        return _ok({"friends": serializer.data, "count": qs.count()})


class FriendDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Unfriend a user", tags=["Friendships"])
    def delete(self, request, friendship_id):
        try:
            friendship = Friendship.objects.get(
                Q(id=friendship_id) &
                (Q(user_a=request.user) | Q(user_b=request.user))
            )
        except Friendship.DoesNotExist:
            return _err("NOT_FOUND", "Friendship not found.", status.HTTP_404_NOT_FOUND)

        friendship.delete()
        logger.info("User %s unfriended via friendship %s", request.user.id, friendship_id)
        return _ok({"message": "Friendship removed."})


# ─── Send Friend Request ──────────────────────────────────────────────────────

class SendFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=SendFriendRequestSerializer, summary="Send a friend request", tags=["Friendships"])
    def post(self, request):
        serializer = SendFriendRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        to_user = serializer.validated_data["to_user"]
        message = serializer.validated_data.get("message", "")

        friend_request = FriendRequest.objects.create(
            from_user = request.user,
            to_user   = to_user,
            message   = message,
        )

        # Send FCM push to recipient (best-effort, non-blocking)
        _push_friend_request(to_user, request.user.name, str(friend_request.id))

        return _ok(
            {"request": FriendRequestSerializer(friend_request).data},
            status.HTTP_201_CREATED,
        )


def _push_friend_request(to_user, requester_name: str, request_id: str):
    """Send FCM notification for friend request — ignores failures."""
    try:
        tokens = list(UserDevice.objects.filter(user=to_user).values_list("fcm_token", flat=True))
        for token in tokens:
            notify_friend_request(token, requester_name, request_id)
    except Exception as e:
        logger.warning("FCM friend request push failed: %s", e)


# ─── Received Requests ────────────────────────────────────────────────────────

class ReceivedFriendRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List incoming pending friend requests", tags=["Friendships"])
    def get(self, request):
        qs = (
            FriendRequest.objects
            .filter(to_user=request.user, status=FriendRequest.Status.PENDING)
            .select_related("from_user")
            .order_by("-created_at")
        )
        serializer = FriendRequestSerializer(qs, many=True)
        return _ok({"requests": serializer.data, "count": qs.count()})


# ─── Sent Requests ────────────────────────────────────────────────────────────

class SentFriendRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List outgoing pending friend requests", tags=["Friendships"])
    def get(self, request):
        qs = (
            FriendRequest.objects
            .filter(from_user=request.user, status=FriendRequest.Status.PENDING)
            .select_related("to_user")
            .order_by("-created_at")
        )
        serializer = FriendRequestSerializer(qs, many=True)
        return _ok({"requests": serializer.data, "count": qs.count()})


# ─── Accept Friend Request ────────────────────────────────────────────────────

class AcceptFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Accept an incoming friend request", tags=["Friendships"])
    def post(self, request, request_id):
        try:
            friend_request = FriendRequest.objects.select_related("from_user").get(
                id      = request_id,
                to_user = request.user,
                status  = FriendRequest.Status.PENDING,
            )
        except FriendRequest.DoesNotExist:
            return _err("NOT_FOUND", "Friend request not found or already handled.", status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            friend_request.accept()

        logger.info(
            "Friend request accepted: from=%s to=%s",
            friend_request.from_user.id, request.user.id,
        )

        # Notify the original requester (best-effort)
        try:
            tokens = list(UserDevice.objects.filter(user=friend_request.from_user).values_list("fcm_token", flat=True))
            from services.fcm_service import send_push
            for token in tokens:
                send_push(
                    device_token      = token,
                    title             = "Friend Request Accepted",
                    body              = f"{request.user.name} accepted your friend request!",
                    data              = {"type": "friend_accepted", "user_id": str(request.user.id)},
                    notification_type = "friend_request",
                )
        except Exception as e:
            logger.warning("FCM accept notification failed: %s", e)

        return _ok({
            "message":       "Friend request accepted.",
            "friendship_id": str(
                Friendship.objects.filter(
                    Q(user_a=request.user, user_b=friend_request.from_user) |
                    Q(user_a=friend_request.from_user, user_b=request.user)
                ).values_list("id", flat=True).first()
            ),
        })


# ─── Decline Friend Request ───────────────────────────────────────────────────

class DeclineFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Decline an incoming friend request", tags=["Friendships"])
    def post(self, request, request_id):
        try:
            friend_request = FriendRequest.objects.get(
                id      = request_id,
                to_user = request.user,
                status  = FriendRequest.Status.PENDING,
            )
        except FriendRequest.DoesNotExist:
            return _err("NOT_FOUND", "Friend request not found.", status.HTTP_404_NOT_FOUND)

        friend_request.decline()
        logger.info("Friend request declined: id=%s", request_id)
        return _ok({"message": "Friend request declined."})


# ─── Cancel Friend Request ────────────────────────────────────────────────────

class CancelFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Cancel an outgoing friend request", tags=["Friendships"])
    def delete(self, request, request_id):
        try:
            friend_request = FriendRequest.objects.get(
                id        = request_id,
                from_user = request.user,
                status    = FriendRequest.Status.PENDING,
            )
        except FriendRequest.DoesNotExist:
            return _err("NOT_FOUND", "Friend request not found.", status.HTTP_404_NOT_FOUND)

        friend_request.cancel()
        logger.info("Friend request cancelled: id=%s", request_id)
        return _ok({"message": "Friend request cancelled."})


# ─── Block User ───────────────────────────────────────────────────────────────

class BlockUserView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=BlockUserSerializer, summary="Block a user", tags=["Friendships"])
    def post(self, request):
        serializer = BlockUserSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        target_user = User.objects.get(id=serializer.validated_data["user_id"])

        with transaction.atomic():
            # Remove any existing friendship silently
            Friendship.objects.unfriend(request.user, target_user)

            # Cancel any pending requests between them
            FriendRequest.objects.filter(
                Q(from_user=request.user, to_user=target_user) |
                Q(from_user=target_user, to_user=request.user),
                status=FriendRequest.Status.PENDING,
            ).update(status=FriendRequest.Status.CANCELLED)

            # Create block
            block = Block.objects.create(blocker=request.user, blocked=target_user)

        logger.info("User %s blocked %s", request.user.id, target_user.id)
        return _ok({"message": "User blocked.", "block_id": str(block.id)}, status.HTTP_201_CREATED)


# ─── Unblock User ─────────────────────────────────────────────────────────────

class UnblockUserView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Unblock a user", tags=["Friendships"])
    def delete(self, request, user_id):
        deleted, _ = Block.objects.filter(blocker=request.user, blocked_id=user_id).delete()
        if not deleted:
            return _err("NOT_FOUND", "Block record not found.", status.HTTP_404_NOT_FOUND)
        logger.info("User %s unblocked %s", request.user.id, user_id)
        return _ok({"message": "User unblocked."})

# ─── Blocked Users List ───────────────────────────────────────────────────────

class BlockedUsersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List all blocked users", tags=["Friendships"])
    def get(self, request):
        blocks = (
            Block.objects
            .filter(blocker=request.user)
            .select_related("blocked")
            .order_by("-created_at")
        )
        serializer = BlockSerializer(blocks, many=True)
        return _ok({"blocked": serializer.data, "count": blocks.count()})


# ─── FCM Device Registration ──────────────────────────────────────────────────

class RegisterDeviceView(APIView):
    """
    Called by the Kotlin app on startup and after FCM token refresh.
    Stores the token so the server can push notifications to this device.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=RegisterDeviceSerializer,
        summary="Register FCM device token for push notifications",
        tags=["Devices"],
    )
    def post(self, request):
        serializer = RegisterDeviceSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        device = serializer.save()
        return _ok({"device_id": str(device.id), "message": "Device registered."}, status.HTTP_201_CREATED)

    @extend_schema(summary="Remove a device token (e.g. on logout)", tags=["Devices"])
    def delete(self, request):
        token = request.data.get("fcm_token")
        if not token:
            return _err("MISSING_TOKEN", "fcm_token is required.")
        UserDevice.objects.filter(user=request.user, fcm_token=token).delete()
        return _ok({"message": "Device token removed."})


# ─── Friend Suggestion (Mutual Friends) ──────────────────────────────────────

class FriendSuggestionsView(APIView):
    """
    Returns up to 20 users who share mutual friends with the requesting user
    but are not yet friends. Simple heuristic: sorted by mutual friend count.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get friend suggestions based on mutual connections", tags=["Friendships"])
    def get(self, request):
        from apps.friendships.models import Friendship as F
        user        = request.user
        friend_ids  = set(F.objects.get_friends(user).values_list("id", flat=True))
        blocked_ids = set(Block.objects.blocked_user_ids(user))
        exclude_ids = friend_ids | blocked_ids | {user.id}

        # Find friends-of-friends
        fof_ids = set()
        for fid in friend_ids:
            try:
                friend_obj = User.objects.get(id=fid)
                fof        = F.objects.get_friends(friend_obj).values_list("id", flat=True)
                fof_ids.update(fof)
            except Exception:
                continue

        candidates = fof_ids - exclude_ids
        if not candidates:
            return _ok({"suggestions": [], "count": 0})

        # Sort by mutual friend count (descending), take top 20
        from apps.accounts.serializers import UserSearchSerializer
        candidate_users = User.objects.filter(id__in=candidates, is_active=True)[:50]
        scored = sorted(
            candidate_users,
            key=lambda u: F.objects.mutual_friends_count(user, u),
            reverse=True,
        )[:20]

        serializer = UserSearchSerializer(scored, many=True, context={"request": request})
        return _ok({"suggestions": serializer.data, "count": len(scored)})
