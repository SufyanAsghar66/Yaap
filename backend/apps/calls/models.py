"""
Calls Models — CallRoom, IceCredential
"""
import hashlib, hmac, time, uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class CallRoom(models.Model):
    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        ANSWERED  = "answered",  "Answered"
        MISSED    = "missed",    "Missed"
        DECLINED  = "declined",  "Declined"
        ENDED     = "ended",     "Ended"

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room_id          = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    caller           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="outgoing_calls")
    callee           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="incoming_calls")
    status           = models.CharField(max_length=10, choices=Status.choices, default=Status.INITIATED, db_index=True)
    started_at       = models.DateTimeField(auto_now_add=True)
    answered_at      = models.DateTimeField(null=True, blank=True)
    ended_at         = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    caller_language  = models.CharField(max_length=5, default="en")
    callee_language  = models.CharField(max_length=5, default="en")

    class Meta:
        db_table = "call_rooms"
        indexes  = [
            models.Index(fields=["caller", "-started_at"]),
            models.Index(fields=["callee", "-started_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["room_id"]),
        ]

    def __str__(self):
        return f"Call {self.caller} → {self.callee} [{self.status}]"

    def answer(self):
        self.status      = self.Status.ANSWERED
        self.answered_at = timezone.now()
        self.save(update_fields=["status", "answered_at"])

    def decline(self):
        self.status   = self.Status.DECLINED
        self.ended_at = timezone.now()
        self.save(update_fields=["status", "ended_at"])

    def end(self):
        now = timezone.now()
        self.status   = self.Status.ENDED
        self.ended_at = now
        if self.answered_at:
            self.duration_seconds = int((now - self.answered_at).total_seconds())
        self.save(update_fields=["status", "ended_at", "duration_seconds"])

    def mark_missed(self):
        self.status   = self.Status.MISSED
        self.ended_at = timezone.now()
        self.save(update_fields=["status", "ended_at"])

    @property
    def is_active(self):
        return self.status in (self.Status.INITIATED, self.Status.ANSWERED)

    @property
    def translation_needed(self):
        return self.caller_language != self.callee_language


class IceCredential(models.Model):
    TURN_TTL = 3600

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room       = models.OneToOneField(CallRoom, on_delete=models.CASCADE, related_name="ice_credential")
    username   = models.CharField(max_length=128)
    credential = models.CharField(max_length=256)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ice_credentials"

    @classmethod
    def generate_for_room(cls, room):
        import base64
        expiry      = int(time.time()) + cls.TURN_TTL
        username    = f"{expiry}:{room.caller_id}"
        secret      = getattr(settings, "COTURN_SECRET", "yaap-turn-secret-change-in-prod")
        raw_hmac    = hmac.new(secret.encode(), username.encode(), digestmod=hashlib.sha1).digest()
        credential  = base64.b64encode(raw_hmac).decode()
        return cls.objects.create(
            room       = room,
            username   = username,
            credential = credential,
            expires_at = timezone.now() + timezone.timedelta(seconds=cls.TURN_TTL),
        )
