from django.contrib import admin
from .models import FriendRequest, Friendship, Block, UserDevice


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display  = ["from_user", "to_user", "status", "created_at", "responded_at"]
    list_filter   = ["status"]
    search_fields = ["from_user__email", "to_user__email"]
    readonly_fields = ["id", "created_at"]


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display  = ["user_a", "user_b", "created_at"]
    search_fields = ["user_a__email", "user_b__email"]
    readonly_fields = ["id", "created_at"]


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display  = ["blocker", "blocked", "created_at"]
    search_fields = ["blocker__email", "blocked__email"]
    readonly_fields = ["id", "created_at"]


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display  = ["user", "device_name", "last_used_at"]
    search_fields = ["user__email"]
    readonly_fields = ["id", "last_used_at"]
