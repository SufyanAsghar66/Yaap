"""Messaging Serializers"""
from django.conf import settings
from rest_framework import serializers
from .models import Conversation, Message, MessageTranslation


class MessageSerializer(serializers.ModelSerializer):
    sender_id    = serializers.UUIDField(source="sender.id",        read_only=True)
    sender_name  = serializers.CharField(source="sender.name",       read_only=True)
    sender_avatar = serializers.CharField(source="sender.avatar_url", read_only=True)
    translation  = serializers.SerializerMethodField()

    class Meta:
        model  = Message
        fields = ["id","conversation_id","sender_id","sender_name","sender_avatar",
                  "content","original_language","status","deleted_for_everyone",
                  "translation","created_at","updated_at"]

    def get_translation(self, obj):
        lang = self.context.get("preferred_language")
        if not lang or lang == obj.original_language or obj.deleted_for_everyone:
            return None
        t = obj.translations.filter(language=lang).first()
        return t.translated_content if t else None


class ConversationSerializer(serializers.ModelSerializer):
    other_user   = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model  = Conversation
        fields = ["id","other_user","last_message","unread_count","created_at","updated_at"]

    def get_other_user(self, obj):
        user  = self.context["request"].user
        other = obj.other_participant(user)
        return {
            "id": str(other.id), "display_name": other.name,
            "avatar_url": other.avatar_url, "country_code": other.country_code,
            "timezone": other.timezone, "is_online": other.is_online,
            "last_seen": other.last_seen.isoformat() if other.last_seen else None,
        }

    def get_last_message(self, obj):
        if not obj.last_message or obj.last_message.deleted_for_everyone:
            return None
        m = obj.last_message
        return {"id": str(m.id), "content": m.content, "sender_id": str(m.sender_id),
                "status": m.status, "created_at": m.created_at.isoformat()}

    def get_unread_count(self, obj):
        user = self.context["request"].user
        return Message.objects.filter(
            conversation=obj, deleted_for_everyone=False,
        ).exclude(sender=user).exclude(status=Message.Status.READ).count()


class TranslateMessageSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=settings.YAAP_SUPPORTED_LANGUAGES)
