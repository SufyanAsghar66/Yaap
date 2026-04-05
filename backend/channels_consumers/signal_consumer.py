"""
Signaling Consumer — Phase 6
Full WebRTC signaling relay between caller and callee.

Connection: ws://host/ws/calls/<room_id>/?token=<jwt>

Client → Server (type field):
  call_offer     { sdp, type:"offer" }
  call_answer    { sdp, type:"answer" }
  ice_candidate  { candidate, sdpMid, sdpMLineIndex }
  call_decline   {}
  call_end       {}
  call_missed    {}

Server → Client:
  signaling.offer        — SDP offer (to callee only)
  signaling.answer       — SDP answer (to caller only)
  signaling.ice          — ICE candidate (to peer only)
  signaling.declined     — call rejected
  signaling.ended        — call ended by peer
  signaling.missed       — no answer timeout
  signaling.peer_joined  — other peer connected
  signaling.peer_left    — other peer disconnected
"""

import json
import logging
from channels.db import database_sync_to_async
from channels_consumers.base_consumer import BaseConsumer

logger = logging.getLogger(__name__)


class SignalingConsumer(BaseConsumer):

    async def connect(self):
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.room_id    = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"signaling_{self.room_id}"

        room = await self._get_room()
        if not room:
            await self.close(code=4003)
            return

        self.room = room
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.channel_layer.group_send(self.group_name, {
            "type": "signaling.peer_joined",
            "payload": {
                "user_id":      str(self.user.id),
                "display_name": self.user.name,
                "avatar_url":   self.user.avatar_url,
                "language":     self.user.language_preference,
                "role":         "caller" if str(room.caller_id) == str(self.user.id) else "callee",
            },
        })
        logger.info("Signaling connected: user=%s room=%s", self.user.id, self.room_id)

    async def disconnect(self, close_code):
        if not hasattr(self, "group_name"):
            return
        await self.channel_layer.group_send(self.group_name, {
            "type": "signaling.peer_left",
            "payload": {"user_id": str(self.user.id), "close_code": close_code},
        })
        room = await self._reload_room()
        if room and room.is_active:
            await self._end_call_db()
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info("Signaling disconnected: user=%s room=%s code=%s", self.user.id, self.room_id, close_code)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data     = json.loads(text_data or "{}")
            msg_type = data.get("type", "")
            payload  = data.get("payload", {})
        except json.JSONDecodeError:
            await self.send_error("INVALID_JSON", "Invalid JSON.")
            return
        handlers = {
            "call_offer":    self._handle_offer,
            "call_answer":   self._handle_answer,
            "ice_candidate": self._handle_ice,
            "call_decline":  self._handle_decline,
            "call_end":      self._handle_end,
            "call_missed":   self._handle_missed,
        }
        handler = handlers.get(msg_type)
        if handler:
            await handler(payload)
        else:
            await self.send_error("UNKNOWN_TYPE", f"Unknown event: {msg_type}")

    # ── Client → Server handlers ──────────────────────────────────────────────

    async def _handle_offer(self, payload):
        if not await self._is_caller():
            await self.send_error("NOT_CALLER", "Only caller can send offer.")
            return
        if not payload.get("sdp"):
            await self.send_error("MISSING_SDP", "sdp required.")
            return
        await self.channel_layer.group_send(self.group_name, {
            "type": "signaling.offer",
            "payload": {
                "sdp": payload["sdp"], "type": "offer",
                "caller_id": str(self.user.id), "caller_name": self.user.name,
                "caller_lang": self.user.language_preference,
            },
        })

    async def _handle_answer(self, payload):
        if await self._is_caller():
            await self.send_error("NOT_CALLEE", "Only callee can answer.")
            return
        if not payload.get("sdp"):
            await self.send_error("MISSING_SDP", "sdp required.")
            return
        await self._answer_call_db()
        await self.channel_layer.group_send(self.group_name, {
            "type": "signaling.answer",
            "payload": {
                "sdp": payload["sdp"], "type": "answer",
                "callee_id": str(self.user.id), "callee_lang": self.user.language_preference,
            },
        })
        logger.info("Call answered: room=%s", self.room_id)

    async def _handle_ice(self, payload):
        await self.channel_layer.group_send(self.group_name, {
            "type": "signaling.ice",
            "payload": {
                "candidate":     payload.get("candidate"),
                "sdpMid":        payload.get("sdpMid"),
                "sdpMLineIndex": payload.get("sdpMLineIndex"),
                "from_user_id":  str(self.user.id),
            },
        })

    async def _handle_decline(self, payload):
        if await self._is_caller():
            await self.send_error("NOT_CALLEE", "Only callee can decline.")
            return
        await self._decline_call_db()
        await self.channel_layer.group_send(self.group_name, {
            "type": "signaling.declined",
            "payload": {"callee_id": str(self.user.id), "reason": payload.get("reason", "declined")},
        })
        logger.info("Call declined: room=%s", self.room_id)

    async def _handle_end(self, payload):
        await self._end_call_db()
        await self.channel_layer.group_send(self.group_name, {
            "type": "signaling.ended",
            "payload": {"ended_by": str(self.user.id), "ended_by_name": self.user.name},
        })
        logger.info("Call ended: room=%s by=%s", self.room_id, self.user.id)

    async def _handle_missed(self, payload):
        if not await self._is_caller():
            return
        await self._missed_call_db()
        await self.channel_layer.group_send(self.group_name, {
            "type": "signaling.missed",
            "payload": {"room_id": self.room_id},
        })

    # ── Group → Consumer dispatchers ──────────────────────────────────────────

    async def signaling_offer(self, event):
        if not await self._is_caller():          # deliver only to callee
            await self.send_event("signaling.offer", event["payload"])

    async def signaling_answer(self, event):
        if await self._is_caller():              # deliver only to caller
            await self.send_event("signaling.answer", event["payload"])

    async def signaling_ice(self, event):
        if event["payload"].get("from_user_id") != str(self.user.id):
            await self.send_event("signaling.ice", event["payload"])

    async def signaling_declined(self, event):
        await self.send_event("signaling.declined", event["payload"])

    async def signaling_ended(self, event):
        await self.send_event("signaling.ended", event["payload"])

    async def signaling_missed(self, event):
        await self.send_event("signaling.missed", event["payload"])

    async def signaling_peer_joined(self, event):
        if event["payload"].get("user_id") != str(self.user.id):
            await self.send_event("signaling.peer_joined", event["payload"])

    async def signaling_peer_left(self, event):
        if event["payload"].get("user_id") != str(self.user.id):
            await self.send_event("signaling.peer_left", event["payload"])

    # ── DB helpers ────────────────────────────────────────────────────────────

    @database_sync_to_async
    def _get_room(self):
        from apps.calls.models import CallRoom
        try:
            return CallRoom.objects.select_related("caller", "callee").get(room_id=self.room_id)
        except CallRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def _reload_room(self):
        from apps.calls.models import CallRoom
        try:
            return CallRoom.objects.get(room_id=self.room_id)
        except CallRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def _is_caller(self) -> bool:
        if hasattr(self, "room"):
            return str(self.room.caller_id) == str(self.user.id)
        return False

    @database_sync_to_async
    def _answer_call_db(self):
        from apps.calls.models import CallRoom
        try:
            r = CallRoom.objects.get(room_id=self.room_id)
            if r.status == CallRoom.Status.INITIATED:
                r.answer()
        except CallRoom.DoesNotExist:
            pass

    @database_sync_to_async
    def _decline_call_db(self):
        from apps.calls.models import CallRoom
        try:
            r = CallRoom.objects.get(room_id=self.room_id)
            if r.status == CallRoom.Status.INITIATED:
                r.decline()
        except CallRoom.DoesNotExist:
            pass

    @database_sync_to_async
    def _end_call_db(self):
        from apps.calls.models import CallRoom
        try:
            r = CallRoom.objects.get(room_id=self.room_id)
            if r.is_active:
                r.end()
        except CallRoom.DoesNotExist:
            pass

    @database_sync_to_async
    def _missed_call_db(self):
        from apps.calls.models import CallRoom
        try:
            r = CallRoom.objects.get(room_id=self.room_id)
            if r.status == CallRoom.Status.INITIATED:
                r.mark_missed()
        except CallRoom.DoesNotExist:
            pass
