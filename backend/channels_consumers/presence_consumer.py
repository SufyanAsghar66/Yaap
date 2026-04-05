"""
Presence Consumer
Tracks user online/offline state via a persistent WebSocket connection.
The Kotlin app maintains one PresenceConsumer connection per session.
When the connection drops the user is automatically marked offline.
"""

import logging
from channels.db import database_sync_to_async
from channels_consumers.base_consumer import BaseConsumer

logger = logging.getLogger(__name__)


class PresenceConsumer(BaseConsumer):
    """
    WebSocket path: ws://host/ws/presence/?token=<jwt>

    Events sent FROM server TO client:
      - presence.friends_online: list of online friend IDs on connect
      - presence.update:         a friend came online / went offline

    Events sent FROM client TO server:
      - ping: heartbeat (client should send every 30s to keep connection alive)
    """

    async def connect(self):
        user = self.user
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        await self.accept()

        # Join the user's personal presence channel
        # Other consumers broadcast to this channel when relevant events happen
        self.personal_group = f"presence_user_{user.id}"
        await self.channel_layer.group_add(self.personal_group, self.channel_name)

        # Mark user online in DB
        await self._mark_online(user)

        # Notify all friends that this user came online
        await self._notify_friends_of_status(user, is_online=True)

        # Send back the list of currently online friends
        online_friends = await self._get_online_friends(user)
        await self.send_event("presence.friends_online", {"online_user_ids": online_friends})

        logger.info("Presence connected: user=%s", user.id)

    async def disconnect(self, close_code):
        user = self.user
        if user and user.is_authenticated:
            await self._mark_offline(user)
            await self._notify_friends_of_status(user, is_online=False)
            await self.channel_layer.group_discard(self.personal_group, self.channel_name)
            logger.info("Presence disconnected: user=%s code=%s", user.id, close_code)

    async def receive(self, text_data=None, bytes_data=None):
        """Only handles ping heartbeats."""
        import json
        try:
            data      = json.loads(text_data or "{}")
            msg_type  = data.get("type")
            if msg_type == "ping":
                await self.send_event("pong", {})
        except Exception as e:
            logger.warning("Presence receive error: %s", e)

    # ─── Channel layer event handlers ────────────────────────────────────────

    async def presence_update(self, event):
        """Relay a friend's presence change to this client."""
        await self.send_event("presence.update", event["payload"])

    # ─── DB helpers ──────────────────────────────────────────────────────────

    @database_sync_to_async
    def _mark_online(self, user):
        user.mark_online()

    @database_sync_to_async
    def _mark_offline(self, user):
        user.mark_offline()

    @database_sync_to_async
    def _get_online_friends(self, user) -> list[str]:
        from apps.friendships.models import Friendship
        friends = Friendship.objects.get_friends(user)
        return [str(f.id) for f in friends if f.is_online]

    @database_sync_to_async
    def _get_friend_ids(self, user) -> list[str]:
        from apps.friendships.models import Friendship
        friends = Friendship.objects.get_friends(user)
        return [str(f.id) for f in friends]

    async def _notify_friends_of_status(self, user, is_online: bool):
        """Broadcast online/offline event to all friends' presence channels."""
        friend_ids = await self._get_friend_ids(user)
        payload    = {
            "user_id":   str(user.id),
            "is_online": is_online,
        }
        for fid in friend_ids:
            await self.channel_layer.group_send(
                f"presence_user_{fid}",
                {"type": "presence.update", "payload": payload},
            )
