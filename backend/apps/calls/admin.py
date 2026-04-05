from django.contrib import admin
from .models import CallRoom, IceCredential

@admin.register(CallRoom)
class CallRoomAdmin(admin.ModelAdmin):
    list_display   = ["caller", "callee", "status", "started_at", "duration_seconds"]
    list_filter    = ["status"]
    search_fields  = ["caller__email", "callee__email"]
    readonly_fields = ["id", "room_id", "started_at", "answered_at", "ended_at"]

@admin.register(IceCredential)
class IceCredentialAdmin(admin.ModelAdmin):
    list_display  = ["room", "username", "expires_at", "created_at"]
    readonly_fields = ["id", "created_at"]
