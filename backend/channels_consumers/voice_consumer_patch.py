"""
Voice Training WebSocket Consumer Extension
Adds the voice.training_update event handler to the PresenceConsumer.

The PresenceConsumer is the user's persistent global WebSocket channel.
When the Celery voice training task completes (or fails), it calls
channel_layer.group_send(..., {"type": "voice.training_update", ...})
which routes to this handler, forwarding the event to the Kotlin app.

This file patches PresenceConsumer at import time — it is imported
in channels_consumers/routing.py AFTER presence_consumer.py so the
method is available on the class before any consumer instances are created.

The Kotlin app listens on the presence WebSocket for:
  { "type": "voice.training_update",
    "payload": { "event": "voice.training_complete"|"voice.training_failed",
                 "voice_trained": true|false,
                 "next_step": "main_chat"|null,
                 "message": "...",
                 "error": "..." } }
"""

# This handler is monkey-patched onto PresenceConsumer via routing.py import order.
# It is defined here as a standalone async method and attached in routing.py.
import logging
logger = logging.getLogger(__name__)


async def voice_training_update(self, event):
    """
    Relay voice training status from Celery task → WebSocket → Kotlin app.
    Attached to PresenceConsumer as an event handler.
    """
    logger.info(
        "Relaying voice.training_update to user %s: %s",
        getattr(self.user, "id", "?"),
        event.get("payload", {}).get("event"),
    )
    await self.send_event("voice.training_update", event["payload"])


# ─── Patch PresenceConsumer at import time ────────────────────────────────────
from channels_consumers.presence_consumer import PresenceConsumer  # noqa: E402

PresenceConsumer.voice_training_update = voice_training_update  # type: ignore
