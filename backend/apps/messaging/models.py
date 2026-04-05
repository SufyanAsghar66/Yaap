"""
Messaging Models — Conversation, Message, MessageDeletion, MessageTranslation
"""
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ConversationManager(models.Manager):
    def get_or_create_between(self, user_a, user_b):
        a, b = _ordered_users(user_a, user_b)
        return self.get_or_create(participant_a=a, participant_b=b)

    def for_user(self, user):
        return (
            self.filter(Q(participant_a=user) | Q(participant_b=user))
            .select_related("participant_a", "participant_b", "last_message")
            .order_by("-updated_at")
        )


class Conversation(models.Model):
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant_a = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_as_a")
    participant_b = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_as_b")
    last_message  = models.ForeignKey("Message", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)
    objects       = ConversationManager()

    class Meta:
        db_table        = "conversations"
        unique_together = [("participant_a", "participant_b")]
        indexes         = [models.Index(fields=["-updated_at"])]

    def save(self, *args, **kwargs):
        if str(self.participant_a_id) > str(self.participant_b_id):
            self.participant_a_id, self.participant_b_id = self.participant_b_id, self.participant_a_id
        super().save(*args, **kwargs)

    def other_participant(self, user):
        return self.participant_b if self.participant_a_id == user.id else self.participant_a


class MessageManager(models.Manager):
    def visible_to(self, user, conversation):
        deleted_for_me = MessageDeletion.objects.filter(user=user).values_list("message_id", flat=True)
        return (
            self.filter(conversation=conversation, deleted_for_everyone=False)
            .exclude(id__in=deleted_for_me)
            .select_related("sender")
            .order_by("-created_at")
        )


class Message(models.Model):
    class Status(models.TextChoices):
        SENT      = "sent",      "Sent"
        DELIVERED = "delivered", "Delivered"
        READ      = "read",      "Read"

    id                   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation         = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender               = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    content              = models.TextField()
    original_language    = models.CharField(max_length=5, default="en")
    status               = models.CharField(max_length=10, choices=Status.choices, default=Status.SENT, db_index=True)
    deleted_for_everyone = models.BooleanField(default=False, db_index=True)
    deleted_at           = models.DateTimeField(null=True, blank=True)
    created_at           = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at           = models.DateTimeField(auto_now=True)
    objects              = MessageManager()

    class Meta:
        db_table = "messages"
        indexes  = [models.Index(fields=["conversation", "-created_at"])]

    def can_delete_for_everyone(self, user) -> bool:
        if self.sender_id != user.id:
            return False
        hours_elapsed = (timezone.now() - self.created_at).total_seconds() / 3600
        return hours_elapsed <= settings.YAAP_MESSAGE_DELETE_WINDOW_HOURS

    def delete_for_everyone(self):
        self.deleted_for_everyone = True
        self.content              = "This message was deleted."
        self.deleted_at           = timezone.now()
        self.save(update_fields=["deleted_for_everyone", "content", "deleted_at"])

    def delete_for_user(self, user):
        MessageDeletion.objects.get_or_create(message=self, user=user)


#class MessageDeletion(models.Model):
   # message    = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="deletions")
    #user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    #deleted_at = models.DateTimeField(auto_now_add=True)

    #class Meta:
     #   db_table        = "message_deletions"
      #  unique_together = [("message", "user")]



class MessageDeletion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  
    message = models.ForeignKey("messaging.Message", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    deleted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["message", "user"], name="unique_message_deletion")
        ]



class MessageTranslation(models.Model):
    id                 = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message            = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="translations")
    language           = models.CharField(max_length=5)
    translated_content = models.TextField()
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = "message_translations"
        unique_together = [("message", "language")]
        indexes         = [models.Index(fields=["message", "language"])]


def _ordered_users(user_a, user_b):
    if str(user_a.id) <= str(user_b.id):
        return user_a, user_b
    return user_b, user_a
