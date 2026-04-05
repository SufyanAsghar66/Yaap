"""
Friendship endpoint tests — Phase 2.
Covers: send request, accept, decline, cancel, unfriend, block, suggestions.
"""

import pytest
from django.utils import timezone
from datetime import timedelta

from apps.friendships.models import Block, FriendRequest, Friendship


def make_friendship(user_a, user_b):
    """Test helper: create an accepted friendship directly."""
    req = FriendRequest.objects.create(
        from_user  = user_a,
        to_user    = user_b,
        expires_at = timezone.now() + timedelta(days=1) if hasattr(FriendRequest, "expires_at") else None,
    )
    req.accept()
    return Friendship.objects.filter(
        __import__("django.db.models", fromlist=["Q"]).Q(user_a=user_a, user_b=user_b) |
        __import__("django.db.models", fromlist=["Q"]).Q(user_a=user_b, user_b=user_a)
    ).first()


# ─── Send Friend Request ──────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSendFriendRequest:

    URL = "/api/v1/friends/request/"

    def test_send_request_success(self, auth_client, user_b):
        client, user = auth_client
        resp = client.post(self.URL, {"to_user_id": str(user_b.id)})
        assert resp.status_code == 201
        assert resp.json()["success"] is True
        assert FriendRequest.objects.filter(from_user=user, to_user=user_b, status="pending").exists()

    def test_cannot_send_to_self(self, auth_client):
        client, user = auth_client
        resp = client.post(self.URL, {"to_user_id": str(user.id)})
        assert resp.status_code == 400

    def test_cannot_send_duplicate_pending(self, auth_client, user_b):
        client, user = auth_client
        FriendRequest.objects.create(from_user=user, to_user=user_b)
        resp = client.post(self.URL, {"to_user_id": str(user_b.id)})
        assert resp.status_code == 400

    def test_cannot_send_to_already_friend(self, auth_client, user_b):
        client, user = auth_client
        FriendRequest.objects.create(from_user=user, to_user=user_b).accept()
        resp = client.post(self.URL, {"to_user_id": str(user_b.id)})
        assert resp.status_code == 400

    def test_cannot_send_to_blocked_user(self, auth_client, user_b):
        client, user = auth_client
        Block.objects.create(blocker=user, blocked=user_b)
        resp = client.post(self.URL, {"to_user_id": str(user_b.id)})
        assert resp.status_code == 400

    def test_cooldown_after_decline(self, auth_client, user_b):
        client, user = auth_client
        req = FriendRequest.objects.create(from_user=user, to_user=user_b)
        req.decline()
        # Try immediately — should be blocked by cooldown
        resp = client.post(self.URL, {"to_user_id": str(user_b.id)})
        assert resp.status_code == 400

    def test_unauthenticated_rejected(self, api_client, user_b):
        resp = api_client.post(self.URL, {"to_user_id": str(user_b.id)})
        assert resp.status_code == 401


# ─── Received Requests ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestReceivedRequests:

    URL = "/api/v1/friends/requests/received/"

    def test_lists_incoming_pending(self, auth_client, user_b):
        client, user = auth_client
        FriendRequest.objects.create(from_user=user_b, to_user=user)
        resp = client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["count"] == 1
        assert data["requests"][0]["from_user"]["id"] == str(user_b.id)

    def test_does_not_show_accepted(self, auth_client, user_b):
        client, user = auth_client
        req = FriendRequest.objects.create(from_user=user_b, to_user=user)
        req.accept()
        resp = client.get(self.URL)
        assert resp.json()["data"]["count"] == 0


# ─── Accept Request ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAcceptFriendRequest:

    def test_accept_creates_friendship(self, auth_client, user_b, mocker):
        mocker.patch("apps.friendships.views.UserDevice")
        mocker.patch("apps.friendships.views.send_push")
        client, user = auth_client
        req = FriendRequest.objects.create(from_user=user_b, to_user=user)
        url = f"/api/v1/friends/requests/{req.id}/accept/"
        resp = client.post(url)
        assert resp.status_code == 200
        req.refresh_from_db()
        assert req.status == "accepted"
        assert Friendship.objects.are_friends(user, user_b)

    def test_cannot_accept_others_request(self, auth_client, user_b, user_c):
        client, user = auth_client
        # Request between user_b and user_c — user should not be able to accept
        req = FriendRequest.objects.create(from_user=user_b, to_user=user_c)
        url = f"/api/v1/friends/requests/{req.id}/accept/"
        resp = client.post(url)
        assert resp.status_code == 404


# ─── Decline Request ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDeclineFriendRequest:

    def test_decline_sets_status(self, auth_client, user_b):
        client, user = auth_client
        req = FriendRequest.objects.create(from_user=user_b, to_user=user)
        url = f"/api/v1/friends/requests/{req.id}/decline/"
        resp = client.post(url)
        assert resp.status_code == 200
        req.refresh_from_db()
        assert req.status == "declined"
        assert not Friendship.objects.are_friends(user, user_b)


# ─── Cancel Sent Request ──────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCancelFriendRequest:

    def test_cancel_own_request(self, auth_client, user_b):
        client, user = auth_client
        req = FriendRequest.objects.create(from_user=user, to_user=user_b)
        url = f"/api/v1/friends/requests/{req.id}/"
        resp = client.delete(url)
        assert resp.status_code == 200
        req.refresh_from_db()
        assert req.status == "cancelled"

    def test_cannot_cancel_others_request(self, auth_client, user_b, user_c):
        client, user = auth_client
        req = FriendRequest.objects.create(from_user=user_b, to_user=user_c)
        url = f"/api/v1/friends/requests/{req.id}/"
        resp = client.delete(url)
        assert resp.status_code == 404


# ─── Unfriend ─────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestUnfriend:

    def test_unfriend_removes_friendship(self, auth_client, user_b, mocker):
        mocker.patch("apps.friendships.views.UserDevice")
        mocker.patch("apps.friendships.views.send_push")
        client, user = auth_client
        req = FriendRequest.objects.create(from_user=user_b, to_user=user)
        req.accept()
        friendship = Friendship.objects.filter(
            __import__("django.db.models", fromlist=["Q"]).Q(user_a=user, user_b=user_b) |
            __import__("django.db.models", fromlist=["Q"]).Q(user_a=user_b, user_b=user)
        ).first()
        url = f"/api/v1/friends/{friendship.id}/"
        resp = client.delete(url)
        assert resp.status_code == 200
        assert not Friendship.objects.are_friends(user, user_b)

    def test_cannot_delete_others_friendship(self, auth_client, user_b, user_c):
        client, user = auth_client
        req = FriendRequest.objects.create(from_user=user_b, to_user=user_c)
        req.accept()
        from django.db.models import Q
        friendship = Friendship.objects.filter(Q(user_a=user_b) | Q(user_b=user_b)).first()
        url = f"/api/v1/friends/{friendship.id}/"
        resp = client.delete(url)
        assert resp.status_code == 404


# ─── Block ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestBlock:

    BLOCK_URL = "/api/v1/friends/block/"

    def test_block_user(self, auth_client, user_b):
        client, user = auth_client
        resp = client.post(self.BLOCK_URL, {"user_id": str(user_b.id)})
        assert resp.status_code == 201
        assert Block.objects.is_blocked(user, user_b)

    def test_block_removes_friendship(self, auth_client, user_b, mocker):
        mocker.patch("apps.friendships.views.UserDevice")
        mocker.patch("apps.friendships.views.send_push")
        client, user = auth_client
        FriendRequest.objects.create(from_user=user_b, to_user=user).accept()
        assert Friendship.objects.are_friends(user, user_b)
        client.post(self.BLOCK_URL, {"user_id": str(user_b.id)})
        assert not Friendship.objects.are_friends(user, user_b)

    def test_cannot_block_self(self, auth_client):
        client, user = auth_client
        resp = client.post(self.BLOCK_URL, {"user_id": str(user.id)})
        assert resp.status_code == 400

    def test_cannot_double_block(self, auth_client, user_b):
        client, user = auth_client
        Block.objects.create(blocker=user, blocked=user_b)
        resp = client.post(self.BLOCK_URL, {"user_id": str(user_b.id)})
        assert resp.status_code == 400

    def test_unblock_user(self, auth_client, user_b):
        client, user = auth_client
        Block.objects.create(blocker=user, blocked=user_b)
        resp = client.delete(f"/api/v1/friends/block/{user_b.id}/")
        assert resp.status_code == 200
        assert not Block.objects.is_blocked(user, user_b)

    def test_blocked_user_not_in_search(self, auth_client, user_b):
        client, user = auth_client
        Block.objects.create(blocker=user, blocked=user_b)
        resp = client.get(f"/api/v1/users/search/?q={user_b.display_name}")
        results = resp.json()["data"]["results"]
        ids = [r["id"] for r in results]
        assert str(user_b.id) not in ids
