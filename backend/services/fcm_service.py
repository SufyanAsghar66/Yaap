"""
Firebase Cloud Messaging Service
Sends push notifications to Android devices for:
  - Incoming messages (when WebSocket is not connected / app in background)
  - Incoming call alerts
  - Friend request notifications
  - Voice training completion
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)

_firebase_app = None


def _get_firebase_app():
    """Lazy-initialize Firebase Admin SDK (singleton)."""
    global _firebase_app
    if _firebase_app is None:
        import firebase_admin
        from firebase_admin import credentials
        try:
            cred         = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized.")
        except Exception as e:
            logger.error("Firebase initialization failed: %s", e)
            raise
    return _firebase_app


def send_push(
    device_token: str,
    title: str,
    body: str,
    data: dict | None = None,
    notification_type: str = "message",
) -> bool:
    """
    Send a push notification to a single device.

    Args:
        device_token:      FCM registration token stored in UserDevice model
        title:             Notification title
        body:              Notification body text
        data:              Extra key-value payload for the app to handle silently
        notification_type: One of: message | call | friend_request | voice_trained

    Returns:
        True on success, False on failure.
    """
    try:
        _get_firebase_app()
        from firebase_admin import messaging

        payload = data or {}
        payload["type"] = notification_type

        message = messaging.Message(
            token        = device_token,
            notification = messaging.Notification(title=title, body=body),
            data         = {k: str(v) for k, v in payload.items()},
            android      = messaging.AndroidConfig(
                priority            = "high",
                notification        = messaging.AndroidNotification(
                    channel_id      = _channel_id(notification_type),
                    priority        = "high",
                    default_sound   = True,
                    default_vibrate_timings = True,
                ),
            ),
        )
        response = messaging.send(message)
        logger.info("FCM push sent. message_id=%s token=%s", response, device_token[:20])
        return True

    except Exception as e:
        logger.error("FCM push failed for token %s: %s", device_token[:20], e)
        return False


def send_push_multicast(device_tokens: list[str], title: str, body: str, data: dict | None = None) -> dict:
    """Send the same notification to multiple devices (up to 500)."""
    if not device_tokens:
        return {"success": 0, "failure": 0}

    try:
        _get_firebase_app()
        from firebase_admin import messaging

        payload = data or {}
        message = messaging.MulticastMessage(
            tokens       = device_tokens[:500],
            notification = messaging.Notification(title=title, body=body),
            data         = {k: str(v) for k, v in payload.items()},
            android      = messaging.AndroidConfig(priority="high"),
        )
        response = messaging.send_each_for_multicast(message)
        return {
            "success": response.success_count,
            "failure": response.failure_count,
        }
    except Exception as e:
        logger.error("FCM multicast failed: %s", e)
        return {"success": 0, "failure": len(device_tokens)}


def _channel_id(notification_type: str) -> str:
    """Map notification type to Android notification channel ID."""
    channels = {
        "message":        "yaap_messages",
        "call":           "yaap_calls",
        "friend_request": "yaap_social",
        "voice_trained":  "yaap_system",
    }
    return channels.get(notification_type, "yaap_general")


# ─── Convenience helpers used by views/consumers ─────────────────────────────

def notify_new_message(recipient_tokens: list[str], sender_name: str, preview: str, conversation_id: str):
    send_push_multicast(
        device_tokens = recipient_tokens,
        title         = sender_name,
        body          = preview,
        data          = {"conversation_id": conversation_id, "type": "message"},
    )


def notify_incoming_call(callee_token: str, caller_name: str, room_id: str, caller_avatar: str = ""):
    send_push(
        device_token      = callee_token,
        title             = "Incoming Call",
        body              = f"{caller_name} is calling you",
        data              = {"room_id": room_id, "caller_name": caller_name, "caller_avatar": caller_avatar},
        notification_type = "call",
    )


def notify_friend_request(recipient_token: str, requester_name: str, request_id: str):
    send_push(
        device_token      = recipient_token,
        title             = "New Friend Request",
        body              = f"{requester_name} sent you a friend request",
        data              = {"request_id": request_id},
        notification_type = "friend_request",
    )


def notify_voice_training_complete(user_token: str):
    send_push(
        device_token      = user_token,
        title             = "Voice Profile Ready!",
        body              = "Your voice has been cloned. You can now make translated calls.",
        notification_type = "voice_trained",
    )
