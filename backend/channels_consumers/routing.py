"""
Django Channels WebSocket URL routing — Phase 7 updated.
"""
from django.urls import re_path
from channels_consumers.chat_consumer        import ChatConsumer
from channels_consumers.signal_consumer      import SignalingConsumer
from channels_consumers.presence_consumer    import PresenceConsumer
from channels_consumers.translation_consumer import TranslationConsumer
import channels_consumers.voice_consumer_patch  # noqa: F401 — patches PresenceConsumer

websocket_urlpatterns = [
    # Real-time messaging
    re_path(r"^ws/chat/(?P<conversation_id>[0-9a-f-]{36})/$",
            ChatConsumer.as_asgi()),

    # WebRTC signaling
    re_path(r"^ws/calls/(?P<room_id>[0-9a-f-]{36})/$",
            SignalingConsumer.as_asgi()),

    # User presence (online/offline, voice training push)
    re_path(r"^ws/presence/$",
            PresenceConsumer.as_asgi()),

    # Real-time audio translation pipeline
    re_path(r"^ws/translate/(?P<room_id>[0-9a-f-]{36})/(?P<direction>caller_audio|callee_audio)/$",
            TranslationConsumer.as_asgi()),
]
