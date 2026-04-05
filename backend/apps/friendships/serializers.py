from django.conf import settings
from rest_framework import serializers

from apps.accounts.serializers import UserMiniSerializer
from .models import Block, FriendRequest, Friendship, UserDevice


# ─── Friend Request ───────────────────────────────────────────────────────────

class SendFriendRequestSerializer(serializers.Serializer):
    to_user_id = serializers.UUIDField()
    message = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")

    def validate_to_user_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        requesting_user = self.context["request"].user

        if str(value) == str(requesting_user.id):
            raise serializers.ValidationError("You cannot send a friend request to yourself.")

        if not User.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("User not found.")

        return value

    def validate(self, attrs):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        requesting_user = self.context["request"].user
        to_user = User.objects.get(id=attrs["to_user_id"])

        allowed, reason = FriendRequest.objects.can_send_request(requesting_user, to_user)
        if not allowed:
            raise serializers.ValidationError({"to_user_id": reason})

        attrs["to_user"] = to_user
        return attrs


class FriendRequestSerializer(serializers.ModelSerializer):
    from_user = UserMiniSerializer(read_only=True)
    to_user = UserMiniSerializer(read_only=True)

    class Meta:
        model = FriendRequest
        fields = ["id", "from_user", "to_user", "status", "message", "created_at", "responded_at"]
        read_only_fields = fields


class FriendRequestMiniSerializer(serializers.ModelSerializer):
    from_user_name = serializers.CharField(source="from_user.name", read_only=True)
    from_user_avatar = serializers.CharField(source="from_user.avatar_url", read_only=True)
    from_user_id = serializers.UUIDField(source="from_user.id", read_only=True)

    class Meta:
        model = FriendRequest
        fields = ["id", "from_user_id", "from_user_name", "from_user_avatar", "message", "created_at"]
        read_only_fields = fields


# ─── Friendship ───────────────────────────────────────────────────────────────

class FriendSerializer(serializers.ModelSerializer):
    friend = serializers.SerializerMethodField()
    friendship_since = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Friendship
        fields = ["id", "friend", "friendship_since"]

    def get_friend(self, obj):
        requesting_user = self.context["request"].user
        other = obj.user_b if obj.user_a_id == requesting_user.id else obj.user_a
        return FriendProfileSerializer(other, context=self.context).data


class FriendProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    display_name = serializers.CharField(allow_blank=True, allow_null=True, default="")
    full_name = serializers.CharField(allow_blank=True, allow_null=True, default="")
    avatar_url = serializers.CharField(allow_blank=True, allow_null=True, default="")
    country_code = serializers.CharField(allow_blank=True, allow_null=True, default="")
    timezone = serializers.CharField(allow_blank=True, allow_null=True, default="UTC")
    language_preference = serializers.CharField(allow_blank=True, allow_null=True, default="en")
    bio = serializers.CharField(allow_blank=True, allow_null=True, default="")
    is_online = serializers.SerializerMethodField()
    last_seen = serializers.SerializerMethodField()
    local_time = serializers.SerializerMethodField()

    def get_is_online(self, obj):
        if not getattr(obj, "show_online_status", True):
            return None
        return getattr(obj, "is_online", False)

    def get_last_seen(self, obj):
        from apps.friendships.models import Friendship as F
        requesting_user = self.context["request"].user
        vis = getattr(obj, "last_seen_visibility", None)
        if vis == "nobody":
            return None
        if vis == "friends":
            if not F.objects.are_friends(requesting_user, obj):
                return None
        return getattr(obj, "last_seen", None)

    def get_local_time(self, obj):
        from zoneinfo import ZoneInfo
        from django.utils import timezone as tz

        try:
            tz_name = getattr(obj, "timezone", None) or "UTC"
            local_now = tz.now().astimezone(ZoneInfo(tz_name))
            return local_now.strftime("%H:%M")
        except Exception:
            return None


# ─── Block ────────────────────────────────────────────────────────────────────

class BlockSerializer(serializers.ModelSerializer):
    blocked_user = UserMiniSerializer(source="blocked", read_only=True)

    class Meta:
        model = Block
        fields = ["id", "blocked_user", "created_at"]
        read_only_fields = fields


class BlockUserSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()

    def validate_user_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        requesting_user = self.context["request"].user

        if str(value) == str(requesting_user.id):
            raise serializers.ValidationError("You cannot block yourself.")
        if not User.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("User not found.")
        if Block.objects.filter(blocker=requesting_user, blocked_id=value).exists():
            raise serializers.ValidationError("You have already blocked this user.")
        return value


# ─── UserDevice (FCM Token) ───────────────────────────────────────────────────

class RegisterDeviceSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(required=False, allow_blank=True, default="")
    fcm_token = serializers.CharField(required=False, allow_blank=False)

    class Meta:
        model = UserDevice
        fields = ["fcm_token", "device_name"]

    def validate(self, attrs):
        raw = self.initial_data or {}

        if not attrs.get("fcm_token"):
            attrs["fcm_token"] = (
                raw.get("fcm_token")
                or raw.get("token")
                or raw.get("device_token")
                or raw.get("registration_token")
            )

        if not attrs.get("device_name"):
            attrs["device_name"] = (
                raw.get("device_name")
                or raw.get("platform")
                or raw.get("device")
                or ""
            )

        if not attrs.get("fcm_token"):
            raise serializers.ValidationError({"fcm_token": "FCM token is required."})

        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        device, _ = UserDevice.objects.update_or_create(
            fcm_token=validated_data["fcm_token"],
            defaults={
                "user": user,
                "device_name": validated_data.get("device_name", ""),
            },
        )
        return device