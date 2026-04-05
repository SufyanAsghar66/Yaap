"""
Chat Consumer — Phase 3 Full Implementation
ws://host/ws/chat/<conversation_id>/?token=<jwt>

Client → Server events (type field):
  send_message, typing_start, typing_stop, mark_read, delete_message, load_history

Server → Client events:
  chat.message_new, chat.message_deleted, chat.typing_start, chat.typing_stop,
  chat.read_receipt, chat.history, error
"""

import json
import logging
from channels.db import database_sync_to_async
from django.conf import settings
from channels_consumers.base_consumer import BaseConsumer

logger = logging.getLogger(__name__)


class ChatConsumer(BaseConsumer):

    async def connect(self):
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.group_name      = f"chat_{self.conversation_id}"
        conversation         = await self._get_conversation()
        if not conversation:
            await self.close(code=4003)
            return
        self.conversation = conversation
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._mark_delivered_on_connect()
        logger.info("ChatConsumer: user=%s conv=%s", self.user.id, self.conversation_id)

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data     = json.loads(text_data or "{}")
            msg_type = data.get("type", "")
            payload  = data.get("payload", {})
        except json.JSONDecodeError:
            await self.send_error("INVALID_JSON", "Message must be valid JSON.")
            return
        handlers = {
            "send_message":   self._handle_send_message,
            "typing_start":   self._handle_typing_start,
            "typing_stop":    self._handle_typing_stop,
            "mark_read":      self._handle_mark_read,
            "delete_message": self._handle_delete_message,
            "load_history":   self._handle_load_history,
        }
        handler = handlers.get(msg_type)
        if handler:
            await handler(payload)
        else:
            await self.send_error("UNKNOWN_TYPE", f"Unknown event: {msg_type}")

    # ── Client → Server handlers ──────────────────────────────────────────────

    async def _handle_send_message(self, payload):
        content = payload.get("content", "").strip()
        if not content:
            await self.send_error("EMPTY_MESSAGE", "Content cannot be empty.")
            return
        if len(content) > 4000:
            await self.send_error("MESSAGE_TOO_LONG", "Max 4000 chars.")
            return
        message = await self._save_message(content)
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.message_new", "payload": await self._serialize_message(message)},
        )
        await self._enqueue_translation(message)
        await self._send_fcm_if_offline(message)

    async def _handle_typing_start(self, payload):
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.typing_start", "payload": {"user_id": str(self.user.id), "user_name": self.user.name}},
        )

    async def _handle_typing_stop(self, payload):
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.typing_stop", "payload": {"user_id": str(self.user.id)}},
        )

    async def _handle_mark_read(self, payload):
        message_id = payload.get("message_id")
        if message_id and await self._mark_message_read(message_id):
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "chat.read_receipt", "payload": {"message_id": message_id, "read_by": str(self.user.id)}},
            )

    async def _handle_delete_message(self, payload):
        message_id = payload.get("message_id")
        scope      = payload.get("scope", "me")
        if scope not in ("everyone", "me"):
            await self.send_error("INVALID_SCOPE", "scope must be 'everyone' or 'me'.")
            return
        result = await self._delete_message(message_id, scope)
        if result == "not_found":
            await self.send_error("NOT_FOUND", "Message not found.")
        elif result == "window_expired":
            await self.send_error("WINDOW_EXPIRED", f"Can only delete for everyone within {settings.YAAP_MESSAGE_DELETE_WINDOW_HOURS}h.")
        elif result == "not_sender":
            await self.send_error("NOT_SENDER", "Only the sender can delete for everyone.")
        elif result == "ok":
            if scope == "everyone":
                await self.channel_layer.group_send(
                    self.group_name,
                    {"type": "chat.message_deleted", "payload": {"message_id": message_id, "scope": "everyone"}},
                )
            else:
                await self.send_event("chat.message_deleted", {"message_id": message_id, "scope": "me"})

    async def _handle_load_history(self, payload):
        cursor    = payload.get("cursor")
        page_size = min(int(payload.get("page_size", 50)), 100)
        messages, next_cursor = await self._load_history(cursor, page_size)
        await self.send_event("chat.history", {"messages": messages, "next_cursor": next_cursor, "has_more": next_cursor is not None})

    # ── Group → Consumer dispatchers ──────────────────────────────────────────

    async def chat_message_new(self, event):
        await self.send_event("chat.message_new", event["payload"])

    async def chat_typing_start(self, event):
        if event["payload"].get("user_id") != str(self.user.id):
            await self.send_event("chat.typing_start", event["payload"])

    async def chat_typing_stop(self, event):
        if event["payload"].get("user_id") != str(self.user.id):
            await self.send_event("chat.typing_stop", event["payload"])

    async def chat_read_receipt(self, event):
        await self.send_event("chat.read_receipt", event["payload"])

    async def chat_message_deleted(self, event):
        await self.send_event("chat.message_deleted", event["payload"])

    # ── DB helpers ────────────────────────────────────────────────────────────

    @database_sync_to_async
    def _get_conversation(self):
        from apps.messaging.models import Conversation
        from django.db.models import Q
        try:
            return Conversation.objects.get(
                Q(id=self.conversation_id) &
                (Q(participant_a=self.user) | Q(participant_b=self.user))
            )
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def _save_message(self, content):
        from apps.messaging.models import Message
        msg = Message.objects.create(
            conversation=self.conversation, sender=self.user,
            content=content, original_language=self.user.language_preference,
        )
        self.conversation.last_message = msg
        self.conversation.save(update_fields=["last_message", "updated_at"])
        return msg

    @database_sync_to_async
    def _mark_delivered_on_connect(self):
        from apps.messaging.models import Message
        Message.objects.filter(
            conversation=self.conversation, status=Message.Status.SENT,
        ).exclude(sender=self.user).update(status=Message.Status.DELIVERED)

    @database_sync_to_async
    def _mark_message_read(self, message_id):
        from apps.messaging.models import Message
        return Message.objects.filter(
            id=message_id, conversation=self.conversation,
        ).exclude(sender=self.user).update(status=Message.Status.READ) > 0

    @database_sync_to_async
    def _delete_message(self, message_id, scope):
        from apps.messaging.models import Message
        try:
            msg = Message.objects.get(id=message_id, conversation=self.conversation)
        except Message.DoesNotExist:
            return "not_found"
        if scope == "everyone":
            if msg.sender_id != self.user.id:
                return "not_sender"
            if not msg.can_delete_for_everyone(self.user):
                return "window_expired"
            msg.delete_for_everyone()
        else:
            msg.delete_for_user(self.user)
        return "ok"

    @database_sync_to_async
    def _load_history(self, cursor, page_size):
        from apps.messaging.models import Message
        from django.utils.dateparse import parse_datetime
        qs = Message.objects.visible_to(self.user, self.conversation)
        if cursor:
            try:
                qs = qs.filter(created_at__lt=parse_datetime(cursor))
            except Exception:
                pass
        batch      = list(qs[:page_size + 1])
        has_more   = len(batch) > page_size
        batch      = batch[:page_size]
        next_cursor = batch[-1].created_at.isoformat() if has_more and batch else None
        return [_serialize_msg(m) for m in batch], next_cursor

    @database_sync_to_async
    def _serialize_message(self, message):
        return _serialize_msg(message)

    @database_sync_to_async
    def _enqueue_translation(self, message):
        other = self.conversation.other_participant(self.user)
        if other.language_preference and other.language_preference != message.original_language:
            from services.translation import translate_message_task
            translate_message_task.apply_async(
                args=[str(message.id), other.language_preference], queue="translation"
            )

    @database_sync_to_async
    def _send_fcm_if_offline(self, message):
        other = self.conversation.other_participant(self.user)
        if not other.is_online:
            from apps.friendships.models import UserDevice
            from services.fcm_service import notify_new_message
            tokens = list(UserDevice.objects.filter(user=other).values_list("fcm_token", flat=True))
            if tokens:
                notify_new_message(tokens, self.user.name, message.content[:80], str(self.conversation.id))


def _serialize_msg(m) -> dict:
    return {
        "id": str(m.id), "conversation_id": str(m.conversation_id),
        "sender": {"id": str(m.sender_id), "display_name": getattr(m.sender, "name", ""), "avatar_url": getattr(m.sender, "avatar_url", "")},
        "content": m.content, "original_language": m.original_language,
        "status": m.status, "deleted_for_everyone": m.deleted_for_everyone,
        "created_at": m.created_at.isoformat(), "updated_at": m.updated_at.isoformat(),
    }
