"""Calls Serializers"""
from rest_framework import serializers
from apps.accounts.serializers import UserMiniSerializer
from .models import CallRoom, IceCredential


class CallRoomSerializer(serializers.ModelSerializer):
    caller = UserMiniSerializer(read_only=True)
    callee = UserMiniSerializer(read_only=True)
    translation_needed = serializers.BooleanField(read_only=True)
    class Meta:
        model  = CallRoom
        fields = ["id","room_id","caller","callee","status","caller_language",
                  "callee_language","translation_needed","started_at",
                  "answered_at","ended_at","duration_seconds"]
        read_only_fields = fields


class CallHistorySerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()
    direction  = serializers.SerializerMethodField()
    class Meta:
        model  = CallRoom
        fields = ["id","room_id","other_user","direction","status","duration_seconds","started_at"]
        read_only_fields = fields
    def get_other_user(self, obj):
        user  = self.context["request"].user
        other = obj.callee if obj.caller_id == user.id else obj.caller
        return {"id": str(other.id), "display_name": other.name,
                "avatar_url": other.avatar_url, "country_code": other.country_code}
    def get_direction(self, obj):
        return "outgoing" if obj.caller_id == self.context["request"].user.id else "incoming"


class InitiateCallSerializer(serializers.Serializer):
    callee_id = serializers.UUIDField()
    def validate_callee_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        req  = self.context["request"].user
        if str(value) == str(req.id):
            raise serializers.ValidationError("Cannot call yourself.")
        try:
            callee = User.objects.get(id=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        from apps.friendships.models import Friendship
        if not Friendship.objects.are_friends(req, callee):
            raise serializers.ValidationError("Must be friends to call.")
        if CallRoom.objects.filter(caller=req, callee=callee,
            status__in=[CallRoom.Status.INITIATED, CallRoom.Status.ANSWERED]).exists():
            raise serializers.ValidationError("Active call already exists.")
        return value
