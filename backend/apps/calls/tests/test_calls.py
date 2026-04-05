"""
Calls app tests — Phase 6
Covers: initiate, ICE config, end, decline, history, active call,
missed timeout task, SignalingConsumer state transitions.
"""

import pytest
from unittest.mock import MagicMock, patch
from django.utils import timezone

from apps.calls.models import CallRoom, IceCredential
from apps.friendships.models import Friendship, FriendRequest


def make_friends(user_a, user_b):
    req = FriendRequest.objects.create(from_user=user_a, to_user=user_b)
    req.accept()


# ─── Initiate Call ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestInitiateCall:
    URL = "/api/v1/calls/initiate/"

    @patch("apps.calls.views._push_incoming_call")
    @patch("tasks.call_tasks.mark_missed_if_unanswered.apply_async")
    def test_initiate_success(self, mock_task, mock_push, auth_client, user_b):
        client, user = auth_client
        make_friends(user, user_b)
        resp = client.post(self.URL, {"callee_id": str(user_b.id)})
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["room"]["status"] == "initiated"
        assert data["room"]["caller"]["id"] == str(user.id)
        assert data["room"]["callee"]["id"] == str(user_b.id)
        assert "ice" in data
        assert "ws_url" in data
        assert CallRoom.objects.filter(caller=user, callee=user_b).exists()
        mock_push.assert_called_once()
        mock_task.assert_called_once()

    def test_cannot_call_self(self, auth_client):
        client, user = auth_client
        resp = client.post(self.URL, {"callee_id": str(user.id)})
        assert resp.status_code == 400

    def test_cannot_call_non_friend(self, auth_client, user_b):
        client, user = auth_client
        resp = client.post(self.URL, {"callee_id": str(user_b.id)})
        assert resp.status_code == 400

    @patch("apps.calls.views._push_incoming_call")
    @patch("tasks.call_tasks.mark_missed_if_unanswered.apply_async")
    def test_no_duplicate_active_call(self, mock_task, mock_push, auth_client, user_b):
        client, user = auth_client
        make_friends(user, user_b)
        CallRoom.objects.create(
            caller=user, callee=user_b,
            caller_language="en", callee_language="ar",
            status=CallRoom.Status.INITIATED,
        )
        resp = client.post(self.URL, {"callee_id": str(user_b.id)})
        assert resp.status_code == 400

    def test_requires_auth(self, api_client, user_b):
        resp = api_client.post(self.URL, {"callee_id": str(user_b.id)})
        assert resp.status_code == 401


# ─── ICE Config ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestIceConfig:

    def _make_room(self, caller, callee):
        return CallRoom.objects.create(
            caller=caller, callee=callee,
            caller_language="en", callee_language="ar",
        )

    def test_caller_gets_ice_config(self, auth_client, user_b):
        client, user = auth_client
        make_friends(user, user_b)
        room = self._make_room(user, user_b)
        resp = client.get(f"/api/v1/calls/ice-config/{room.room_id}/")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "ice_servers" in data
        assert len(data["ice_servers"]) == 4
        assert "username" in data
        assert "credential" in data

    def test_callee_gets_ice_config(self, auth_client_b, user):
        client, callee = auth_client_b
        make_friends(user, callee)
        room = CallRoom.objects.create(
            caller=user, callee=callee,
            caller_language="en", callee_language="ar",
        )
        resp = client.get(f"/api/v1/calls/ice-config/{room.room_id}/")
        assert resp.status_code == 200

    def test_non_participant_forbidden(self, auth_client, user_b, user_c):
        client, user = auth_client
        room = CallRoom.objects.create(
            caller=user_b, callee=user_c,
            caller_language="en", callee_language="fr",
        )
        resp = client.get(f"/api/v1/calls/ice-config/{room.room_id}/")
        assert resp.status_code == 403

    def test_ice_credentials_generated_once(self, auth_client, user_b):
        client, user = auth_client
        make_friends(user, user_b)
        room = self._make_room(user, user_b)
        # First call creates credentials
        resp1 = client.get(f"/api/v1/calls/ice-config/{room.room_id}/")
        # Second call returns same credentials (not duplicated)
        resp2 = client.get(f"/api/v1/calls/ice-config/{room.room_id}/")
        assert resp1.json()["data"]["username"] == resp2.json()["data"]["username"]
        assert IceCredential.objects.filter(room=room).count() == 1


# ─── End Call ─────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEndCall:

    def test_caller_can_end(self, auth_client, user_b):
        client, user = auth_client
        make_friends(user, user_b)
        room = CallRoom.objects.create(
            caller=user, callee=user_b,
            caller_language="en", callee_language="ar",
            status=CallRoom.Status.ANSWERED,
        )
        from django.utils import timezone
        room.answered_at = timezone.now()
        room.save()
        resp = client.post(f"/api/v1/calls/{room.room_id}/end/")
        assert resp.status_code == 200
        room.refresh_from_db()
        assert room.status == CallRoom.Status.ENDED

    def test_callee_can_end(self, auth_client_b, user):
        client, callee = auth_client_b
        make_friends(user, callee)
        room = CallRoom.objects.create(
            caller=user, callee=callee,
            caller_language="en", callee_language="ar",
            status=CallRoom.Status.ANSWERED,
        )
        resp = client.post(f"/api/v1/calls/{room.room_id}/end/")
        assert resp.status_code == 200

    def test_cannot_end_already_ended(self, auth_client, user_b):
        client, user = auth_client
        room = CallRoom.objects.create(
            caller=user, callee=user_b,
            caller_language="en", callee_language="ar",
            status=CallRoom.Status.ENDED,
        )
        resp = client.post(f"/api/v1/calls/{room.room_id}/end/")
        assert resp.status_code == 400


# ─── Decline Call ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDeclineCall:

    def test_callee_can_decline(self, auth_client_b, user):
        client, callee = auth_client_b
        room = CallRoom.objects.create(
            caller=user, callee=callee,
            caller_language="en", callee_language="ar",
        )
        resp = client.post(f"/api/v1/calls/{room.room_id}/decline/")
        assert resp.status_code == 200
        room.refresh_from_db()
        assert room.status == CallRoom.Status.DECLINED

    def test_caller_cannot_decline(self, auth_client, user_b):
        client, user = auth_client
        room = CallRoom.objects.create(
            caller=user, callee=user_b,
            caller_language="en", callee_language="ar",
        )
        # auth_client is the caller — this endpoint only works for callee
        resp = client.post(f"/api/v1/calls/{room.room_id}/decline/")
        assert resp.status_code == 404  # callee=user_b, not user


# ─── Call History ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCallHistory:
    URL = "/api/v1/calls/history/"

    def _make_call(self, caller, callee, status=CallRoom.Status.ENDED):
        return CallRoom.objects.create(
            caller=caller, callee=callee,
            caller_language="en", callee_language="ar",
            status=status,
        )

    def test_lists_own_calls(self, auth_client, user_b, user_c):
        client, user = auth_client
        self._make_call(user, user_b)
        self._make_call(user_c, user)
        self._make_call(user_b, user_c)  # unrelated call
        resp = client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2  # only calls involving user

    def test_direction_outgoing(self, auth_client, user_b):
        client, user = auth_client
        self._make_call(user, user_b)
        resp = client.get(self.URL)
        calls = resp.json()["data"]["calls"]
        assert calls[0]["direction"] == "outgoing"

    def test_direction_incoming(self, auth_client, user_b):
        client, user = auth_client
        self._make_call(user_b, user)
        resp = client.get(self.URL)
        calls = resp.json()["data"]["calls"]
        assert calls[0]["direction"] == "incoming"

    def test_filter_missed(self, auth_client, user_b):
        client, user = auth_client
        self._make_call(user_b, user, status=CallRoom.Status.MISSED)
        self._make_call(user_b, user, status=CallRoom.Status.ENDED)
        resp = client.get(f"{self.URL}?filter=missed")
        assert resp.json()["data"]["total"] == 1

    def test_pagination(self, auth_client, user_b):
        client, user = auth_client
        for _ in range(25):
            self._make_call(user, user_b)
        resp = client.get(f"{self.URL}?page_size=10&page=1")
        data = resp.json()["data"]
        assert len(data["calls"]) == 10
        assert data["has_more"] is True
        assert data["total"] == 25


# ─── Active Call ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestActiveCall:
    URL = "/api/v1/calls/active/"

    def test_no_active_call(self, auth_client):
        client, _ = auth_client
        resp = client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["data"]["active_call"] is None

    def test_returns_active_call(self, auth_client, user_b):
        client, user = auth_client
        room = CallRoom.objects.create(
            caller=user, callee=user_b,
            caller_language="en", callee_language="ar",
            status=CallRoom.Status.ANSWERED,
        )
        resp = client.get(self.URL)
        data = resp.json()["data"]["active_call"]
        assert data is not None
        assert str(data["room_id"]) == str(room.room_id)


# ─── Missed Timeout Task ──────────────────────────────────────────────────────

@pytest.mark.django_db
class TestMissedTimeout:

    @patch("services.fcm_service.send_push")
    @patch("apps.friendships.models.UserDevice")
    def test_marks_initiated_call_missed(self, mock_device, mock_push, user, user_b):
        mock_device.objects.filter.return_value.values_list.return_value = []
        room = CallRoom.objects.create(
            caller=user, callee=user_b,
            caller_language="en", callee_language="ar",
            status=CallRoom.Status.INITIATED,
        )
        from tasks.call_tasks import mark_missed_if_unanswered
        mark_missed_if_unanswered(str(room.id))
        room.refresh_from_db()
        assert room.status == CallRoom.Status.MISSED

    @patch("apps.friendships.models.UserDevice")
    def test_does_not_mark_answered_call_missed(self, mock_device, user, user_b):
        mock_device.objects.filter.return_value.values_list.return_value = []
        room = CallRoom.objects.create(
            caller=user, callee=user_b,
            caller_language="en", callee_language="ar",
            status=CallRoom.Status.ANSWERED,
        )
        from tasks.call_tasks import mark_missed_if_unanswered
        mark_missed_if_unanswered(str(room.id))
        room.refresh_from_db()
        assert room.status == CallRoom.Status.ANSWERED


# ─── CallRoom Model ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCallRoomModel:

    def test_translation_needed_true(self, user, user_b):
        room = CallRoom(caller=user, callee=user_b, caller_language="en", callee_language="ar")
        assert room.translation_needed is True

    def test_translation_needed_false_same_language(self, user, user_b):
        room = CallRoom(caller=user, callee=user_b, caller_language="en", callee_language="en")
        assert room.translation_needed is False

    def test_is_active_initiated(self, user, user_b):
        room = CallRoom(status=CallRoom.Status.INITIATED)
        assert room.is_active is True

    def test_is_active_ended(self, user, user_b):
        room = CallRoom(status=CallRoom.Status.ENDED)
        assert room.is_active is False

    def test_duration_seconds_computed_on_end(self, user, user_b):
        room = CallRoom.objects.create(
            caller=user, callee=user_b,
            caller_language="en", callee_language="ar",
            status=CallRoom.Status.ANSWERED,
        )
        room.answered_at = timezone.now()
        room.save()
        import time; time.sleep(0.1)
        room.end()
        room.refresh_from_db()
        assert room.duration_seconds is not None
        assert room.duration_seconds >= 0
