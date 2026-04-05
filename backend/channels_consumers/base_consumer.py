"""
Base WebSocket Consumer
Provides shared helpers:
  - JSON send helper
  - Error send helper
  - User extraction from scope
  - Channel group join/leave
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class BaseConsumer(AsyncWebsocketConsumer):
    """
    Abstract base consumer.
    All YAAP consumers inherit from this to share utilities.
    """

    async def send_json(self, content: dict):
        """Send a JSON-serializable dict to the WebSocket client."""
        await self.send(text_data=json.dumps(content))

    async def send_error(self, code: str, message: str):
        """Send a structured error event to the client."""
        await self.send_json({
            "type":    "error",
            "payload": {"code": code, "message": message},
        })

    async def send_event(self, event_type: str, payload: dict):
        """Send a typed event envelope."""
        await self.send_json({
            "type":    event_type,
            "payload": payload,
        })

    @property
    def user(self):
        return self.scope["user"]

    async def websocket_disconnect(self, message):
        logger.debug(
            "WebSocket disconnected: user=%s path=%s",
            getattr(self.user, "id", "anon"),
            self.scope.get("path"),
        )
        await super().websocket_disconnect(message)
