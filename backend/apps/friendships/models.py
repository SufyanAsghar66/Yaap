"""
Friendships Models
Covers: FriendRequest, Friendship (accepted), Block.

Design decisions:
  - Friendship stores user_a < user_b (UUID ordering) to ensure uniqueness
    without needing a separate unique_together constraint on both orderings.
  - Managers expose high-level query methods used across the codebase.
  - FriendRequest enforces a 7-day cooldown before re-sending after a decline.
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta


# ─── Friendship Manager ───────────────────────────────────────────────────────

class FriendshipManager(models.Manager):

    def are_friends(self, user_a, user_b) -> bool:
        """Check if two users are friends. Order-independent."""
        a, b = _ordered(user_a, user_b)
        return self.filter(user_a=a, user_b=b).exists()

    def get_friends(self, user):
        """Return a queryset of User objects who are friends with `user`."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        qs   = self.filter(models.Q(user_a=user) | models.Q(user_b=user))
        # Collect the other side's IDs
        friend_ids = []
        for f in qs.values("user_a_id", "user_b_id"):
            oid = f["user_b_id"] if f["user_a_id"] == user.id else f["user_a_id"]
            friend_ids.append(oid)
        return User.objects.filter(id__in=friend_ids, is_active=True)

    def mutual_friends_count(self, user_a, user_b) -> int:
        """Count mutual friends between two users."""
        friends_a = set(self.get_friends(user_a).values_list("id", flat=True))
        friends_b = set(self.get_friends(user_b).values_list("id", flat=True))
        return len(friends_a & friends_b)

    def unfriend(self, user_a, user_b) -> bool:
        """Remove a friendship. Returns True if a record was deleted."""
        a, b     = _ordered(user_a, user_b)
        deleted, _ = self.filter(user_a=a, user_b=b).delete()
        return deleted > 0


# ─── FriendRequest Manager ────────────────────────────────────────────────────

class FriendRequestManager(models.Manager):

    def can_send_request(self, from_user, to_user) -> tuple[bool, str]:
        """
        Returns (allowed: bool, reason: str).
        Checks:
          1. Not already friends
          2. No pending request in either direction
          3. Not blocked
          4. Cooldown period after decline
        """
        from apps.friendships.models import Block

        if Friendship.objects.are_friends(from_user, to_user):
            return False, "You are already friends."

        if Block.objects.is_blocked(from_user, to_user):
            return False, "Cannot send request."

        # Pending request from me to them
        if self.filter(from_user=from_user, to_user=to_user, status=FriendRequest.Status.PENDING).exists():
            return False, "You already sent a friend request to this user."

        # Pending request from them to me (should accept instead)
        if self.filter(from_user=to_user, to_user=from_user, status=FriendRequest.Status.PENDING).exists():
            return False, "This user already sent you a friend request. Accept it instead."

        # Cooldown after decline
        cooldown_cutoff = timezone.now() - timedelta(days=settings.YAAP_FRIEND_REQUEST_COOLDOWN_DAYS)
        if self.filter(
            from_user=from_user,
            to_user=to_user,
            status=FriendRequest.Status.DECLINED,
            responded_at__gte=cooldown_cutoff,
        ).exists():
            return False, f"You can re-send a request after {settings.YAAP_FRIEND_REQUEST_COOLDOWN_DAYS} days."

        return True, "ok"


# ─── Block Manager ────────────────────────────────────────────────────────────

class BlockManager(models.Manager):

    def is_blocked(self, user_a, user_b) -> bool:
        """Returns True if either user has blocked the other."""
        return self.filter(
            models.Q(blocker=user_a, blocked=user_b) |
            models.Q(blocker=user_b, blocked=user_a)
        ).exists()

    def blocked_user_ids(self, user) -> list:
        """Return IDs of all users blocked by OR blocking `user`."""
        qs = self.filter(models.Q(blocker=user) | models.Q(blocked=user))
        ids = set()
        for b in qs.values("blocker_id", "blocked_id"):
            ids.add(b["blocker_id"])
            ids.add(b["blocked_id"])
        ids.discard(user.id)
        return list(ids)


# ─── Models ───────────────────────────────────────────────────────────────────

class FriendRequest(models.Model):

    class Status(models.TextChoices):
        PENDING   = "pending",   "Pending"
        ACCEPTED  = "accepted",  "Accepted"
        DECLINED  = "declined",  "Declined"
        CANCELLED = "cancelled", "Cancelled"

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_user    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="sent_friend_requests",
    )
    to_user      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="received_friend_requests",
    )
    status       = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    message      = models.CharField(max_length=200, blank=True, default="",
                                     help_text="Optional short message from requester")

    objects = FriendRequestManager()

    class Meta:
        db_table = "friend_requests"
        unique_together = [("from_user", "to_user", "status")]
        indexes = [
            models.Index(fields=["to_user", "status"]),
            models.Index(fields=["from_user", "status"]),
        ]

    def __str__(self):
        return f"{self.from_user} → {self.to_user} [{self.status}]"

    def accept(self):
        """Accept the request: create Friendship record, mark request accepted."""
        self.status       = self.Status.ACCEPTED
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])

        a, b = _ordered(self.from_user, self.to_user)
        Friendship.objects.get_or_create(user_a=a, user_b=b)

    def decline(self):
        self.status       = self.Status.DECLINED
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])

    def cancel(self):
        self.status       = self.Status.CANCELLED
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])


class Friendship(models.Model):
    """
    Represents an accepted, bidirectional friendship.
    user_a.id < user_b.id (UUID lex order) is enforced in save()
    to prevent duplicate rows for the same pair.
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_a     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="friendships_as_a",
    )
    user_b     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="friendships_as_b",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = FriendshipManager()

    class Meta:
        db_table        = "friendships"
        unique_together = [("user_a", "user_b")]
        indexes         = [
            models.Index(fields=["user_a"]),
            models.Index(fields=["user_b"]),
        ]

    def save(self, *args, **kwargs):
        # Enforce user_a < user_b ordering
        if str(self.user_a_id) > str(self.user_b_id):
            self.user_a_id, self.user_b_id = self.user_b_id, self.user_a_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_a} ↔ {self.user_b}"


class Block(models.Model):
    """Directional block: blocker has blocked blocked_user."""
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blocker    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="blocks_made",
    )
    blocked    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="blocks_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BlockManager()

    class Meta:
        db_table        = "blocks"
        unique_together = [("blocker", "blocked")]

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked}"


# ─── Utility ──────────────────────────────────────────────────────────────────

def _ordered(user_a, user_b):
    """Return (user_a, user_b) with lexicographically smaller UUID first."""
    a_id = str(user_a.id if hasattr(user_a, "id") else user_a)
    b_id = str(user_b.id if hasattr(user_b, "id") else user_b)
    if a_id <= b_id:
        return user_a, user_b
    return user_b, user_a


class UserDevice(models.Model):
    """
    Stores FCM device tokens per user.
    A user may have multiple devices (phone + tablet).
    """
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="devices",
    )
    fcm_token    = models.TextField(unique=True)
    device_name  = models.CharField(max_length=100, blank=True, default="")
    created_at   = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_devices"
        indexes  = [models.Index(fields=["user"])]

    def __str__(self):
        return f"{self.user} — {self.device_name or 'device'}"
