"""Calls REST Views"""
import logging
from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import CallRoom, IceCredential
from .serializers import CallHistorySerializer, CallRoomSerializer, InitiateCallSerializer

logger = logging.getLogger(__name__)
User   = get_user_model()

def _ok(d, sc=status.HTTP_200_OK):  return Response({"success": True,  "data": d}, status=sc)
def _err(c, m, sc=status.HTTP_400_BAD_REQUEST): return Response({"success": False, "error": {"code": c, "message": m}}, status=sc)


class InitiateCallView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = InitiateCallSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        callee = User.objects.get(id=s.validated_data["callee_id"])
        caller = request.user
        room   = CallRoom.objects.create(
            caller=caller, callee=callee,
            caller_language=caller.language_preference,
            callee_language=callee.language_preference,
        )
        ice_cred = IceCredential.generate_for_room(room)
        _push_incoming_call(callee, caller, room)

        from tasks.call_tasks import mark_missed_if_unanswered
        mark_missed_if_unanswered.apply_async(args=[str(room.id)], countdown=30, queue="default")

        logger.info("Call initiated: room=%s caller=%s callee=%s", room.room_id, caller.id, callee.id)
        return _ok({
            "room":    CallRoomSerializer(room).data,
            "ice":     {"username": ice_cred.username, "credential": ice_cred.credential, "expires_at": ice_cred.expires_at.isoformat()},
            "ws_url":  f"ws://{{host}}/ws/calls/{room.room_id}/",
        }, status.HTTP_201_CREATED)


class IceConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        try:
            room = CallRoom.objects.select_related("ice_credential").get(room_id=room_id)
        except CallRoom.DoesNotExist:
            return _err("NOT_FOUND", "Call room not found.", status.HTTP_404_NOT_FOUND)
        if request.user.id not in (room.caller_id, room.callee_id):
            return _err("FORBIDDEN", "Not a participant.", status.HTTP_403_FORBIDDEN)
        try:
            cred = room.ice_credential
        except IceCredential.DoesNotExist:
            cred = IceCredential.generate_for_room(room)

        from django.conf import settings
        turn_host = getattr(settings, "COTURN_HOST", "turn.yaap.app")
        turn_port = getattr(settings, "COTURN_PORT", 3478)
        ice_servers = [
            {"urls": "stun:stun.l.google.com:19302"},
            {"urls": "stun:stun1.l.google.com:19302"},
            {"urls": f"turn:{turn_host}:{turn_port}", "username": cred.username, "credential": cred.credential},
            {"urls": f"turns:{turn_host}:{turn_port}?transport=tcp", "username": cred.username, "credential": cred.credential},
        ]
        return _ok({"ice_servers": ice_servers, "username": cred.username, "credential": cred.credential,
                    "expires_at": cred.expires_at.isoformat(), "room_id": str(room.room_id)})


class EndCallView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        try:
            room = CallRoom.objects.get(room_id=room_id)
        except CallRoom.DoesNotExist:
            return _err("NOT_FOUND", "Call not found.", status.HTTP_404_NOT_FOUND)
        if request.user.id not in (room.caller_id, room.callee_id):
            return _err("FORBIDDEN", "Not a participant.", status.HTTP_403_FORBIDDEN)
        if not room.is_active:
            return _err("NOT_ACTIVE", f"Call is already {room.status}.")
        room.end()
        return _ok({"message": "Call ended.", "duration_seconds": room.duration_seconds})


class DeclineCallView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        try:
            room = CallRoom.objects.get(room_id=room_id, callee=request.user)
        except CallRoom.DoesNotExist:
            return _err("NOT_FOUND", "Call not found.", status.HTTP_404_NOT_FOUND)
        if room.status != CallRoom.Status.INITIATED:
            return _err("NOT_RINGING", "Call is not ringing.")
        room.decline()
        return _ok({"message": "Call declined."})


class CallHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page      = max(1, int(request.query_params.get("page", 1)))
        page_size = min(int(request.query_params.get("page_size", 20)), 50)
        filter_by = request.query_params.get("filter", "all")

        qs = CallRoom.objects.filter(
            Q(caller=request.user) | Q(callee=request.user)
        ).select_related("caller", "callee").order_by("-started_at")

        if filter_by == "missed":    qs = qs.filter(callee=request.user, status=CallRoom.Status.MISSED)
        elif filter_by == "incoming": qs = qs.filter(callee=request.user)
        elif filter_by == "outgoing": qs = qs.filter(caller=request.user)

        total  = qs.count()
        offset = (page - 1) * page_size
        calls  = qs[offset: offset + page_size]
        s      = CallHistorySerializer(calls, many=True, context={"request": request})
        return _ok({"calls": s.data, "total": total, "page": page, "page_size": page_size, "has_more": offset + page_size < total})


class ActiveCallView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        room = CallRoom.objects.filter(
            Q(caller=request.user) | Q(callee=request.user),
            status__in=[CallRoom.Status.INITIATED, CallRoom.Status.ANSWERED],
        ).select_related("caller", "callee").order_by("-started_at").first()
        return _ok({"active_call": CallRoomSerializer(room).data if room else None})


def _push_incoming_call(callee, caller, room):
    try:
        from apps.friendships.models import UserDevice
        from services.fcm_service import notify_incoming_call
        tokens = list(UserDevice.objects.filter(user=callee).values_list("fcm_token", flat=True))
        for token in tokens:
            notify_incoming_call(token, caller.name, str(room.room_id), caller.avatar_url)
    except Exception as e:
        logger.warning("FCM call push failed: %s", e)
