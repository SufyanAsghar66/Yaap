"""
Messaging tests — Phase 3
Covers: conversation create, message send, history, translate, delete.
"""
import pytest
from unittest.mock import patch
from apps.messaging.models import Conversation, Message, MessageTranslation
from apps.friendships.models import FriendRequest


# ─── Conversation ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestConversation:

    def test_start_conversation_between_friends(self, auth_client, user_b, friends):
        client, user = auth_client
        resp = client.post("/api/v1/conversations/start/", {"user_id": str(user_b.id)})
        assert resp.status_code in (200, 201)
        assert "conversation" in resp.json()["data"]

    def test_cannot_start_with_non_friend(self, auth_client, user_b):
        client, _ = auth_client
        resp = client.post("/api/v1/conversations/start/", {"user_id": str(user_b.id)})
        assert resp.status_code == 403

    def test_idempotent_start(self, auth_client, user_b, friends):
        client, _ = auth_client
        resp1 = client.post("/api/v1/conversations/start/", {"user_id": str(user_b.id)})
        resp2 = client.post("/api/v1/conversations/start/", {"user_id": str(user_b.id)})
        id1 = resp1.json()["data"]["conversation"]["id"]
        id2 = resp2.json()["data"]["conversation"]["id"]
        assert id1 == id2

    def test_conversation_list_shows_own(self, auth_client, conversation):
        client, _ = auth_client
        resp = client.get("/api/v1/conversations/")
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json()["data"]["conversations"]]
        assert str(conversation.id) in ids

    def test_requires_auth(self, api_client):
        assert api_client.get("/api/v1/conversations/").status_code == 401


# ─── Messages ─────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestMessages:

    @patch("apps.messaging.views.translate_message_task.apply_async")
    def test_send_message(self, mock_task, auth_client, conversation):
        client, user = auth_client
        resp = client.post(
            f"/api/v1/conversations/{conversation.id}/messages/",
            {"content": "Hello from test!"},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["message"]["content"] == "Hello from test!"
        assert Message.objects.filter(conversation=conversation).count() == 1

    def test_send_empty_message_rejected(self, auth_client, conversation):
        client, _ = auth_client
        resp = client.post(f"/api/v1/conversations/{conversation.id}/messages/", {"content": ""})
        assert resp.status_code == 400

    def test_send_too_long_rejected(self, auth_client, conversation):
        client, _ = auth_client
        resp = client.post(
            f"/api/v1/conversations/{conversation.id}/messages/",
            {"content": "x" * 4001},
        )
        assert resp.status_code == 400

    @patch("apps.messaging.views.translate_message_task.apply_async")
    def test_message_history_pagination(self, mock_task, auth_client, conversation):
        client, user = auth_client
        for i in range(5):
            Message.objects.create(
                conversation=conversation, sender=user,
                content=f"Message {i}", original_language="en",
            )
        resp = client.get(
            f"/api/v1/conversations/{conversation.id}/messages/",
            {"page_size": 3},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["messages"]) == 3
        assert data["has_more"] is True

    def test_non_participant_cannot_read(self, auth_client_c, conversation):
        client, _ = auth_client_c
        resp = client.get(f"/api/v1/conversations/{conversation.id}/messages/")
        assert resp.status_code == 404


# ─── Delete Message ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDeleteMessage:

    def _msg(self, conv, sender):
        return Message.objects.create(
            conversation=conv, sender=sender, content="delete me", original_language="en"
        )

    def test_delete_for_me(self, auth_client, conversation, user):
        client, user = auth_client
        msg = self._msg(conversation, user)
        resp = client.delete(
            f"/api/v1/conversations/messages/{msg.id}/",
            {"scope": "me"}, format="json",
        )
        assert resp.status_code == 200
        from apps.messaging.models import MessageDeletion
        assert MessageDeletion.objects.filter(message=msg, user=user).exists()

    def test_delete_for_everyone_by_sender(self, auth_client, conversation, user):
        client, user = auth_client
        msg = self._msg(conversation, user)
        resp = client.delete(
            f"/api/v1/conversations/messages/{msg.id}/",
            {"scope": "everyone"}, format="json",
        )
        assert resp.status_code == 200
        msg.refresh_from_db()
        assert msg.deleted_for_everyone is True

    def test_non_sender_cannot_delete_for_everyone(self, auth_client_b, conversation, user):
        client, user_b = auth_client_b
        msg = self._msg(conversation, user)
        resp = client.delete(
            f"/api/v1/conversations/messages/{msg.id}/",
            {"scope": "everyone"}, format="json",
        )
        assert resp.status_code == 403


# ─── Translate Message ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTranslateMessage:

    @patch("apps.messaging.views.translate")
    def test_translate_success(self, mock_translate, auth_client, conversation, user):
        mock_translate.return_value = "مرحبا"
        client, _ = auth_client
        msg = Message.objects.create(
            conversation=conversation, sender=user, content="Hello", original_language="en"
        )
        resp = client.post(
            f"/api/v1/conversations/messages/{msg.id}/translate/",
            {"language": "ar"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["translated_content"] == "مرحبا"
        assert data["language"] == "ar"
        assert data["cached"] is False

    @patch("apps.messaging.views.translate")
    def test_translate_returns_cached(self, mock_translate, auth_client, conversation, user):
        client, _ = auth_client
        msg = Message.objects.create(
            conversation=conversation, sender=user, content="Hello", original_language="en"
        )
        MessageTranslation.objects.create(message=msg, language="ar", translated_content="مرحبا مخبأ")
        resp = client.post(
            f"/api/v1/conversations/messages/{msg.id}/translate/",
            {"language": "ar"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["cached"] is True
        assert resp.json()["data"]["translated_content"] == "مرحبا مخبأ"
        mock_translate.assert_not_called()

    def test_translate_unsupported_language_rejected(self, auth_client, conversation, user):
        client, _ = auth_client
        msg = Message.objects.create(
            conversation=conversation, sender=user, content="Hello", original_language="en"
        )
        resp = client.post(
            f"/api/v1/conversations/messages/{msg.id}/translate/",
            {"language": "xx"},
        )
        assert resp.status_code == 400
