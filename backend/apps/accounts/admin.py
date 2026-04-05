from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, EmailOTP


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering       = ["-created_at"]
    list_display   = ["email", "display_name", "auth_provider", "is_verified", "voice_trained", "is_online", "created_at"]
    list_filter    = ["auth_provider", "is_verified", "voice_trained", "is_online", "is_active", "is_staff"]
    search_fields  = ["email", "full_name", "display_name", "supabase_uid"]
    readonly_fields = ["id", "supabase_uid", "created_at", "updated_at", "last_seen"]

    fieldsets = (
        (_("Identity"),    {"fields": ("id", "email", "supabase_uid", "auth_provider")}),
        (_("Profile"),     {"fields": ("full_name", "display_name", "avatar_url", "bio", "date_of_birth", "country_code", "timezone")}),
        (_("Language"),    {"fields": ("language_preference", "voice_trained", "voice_embedding")}),
        (_("Onboarding"),  {"fields": ("profile_complete", "language_selected")}),
        (_("Presence"),    {"fields": ("is_online", "last_seen")}),
        (_("Privacy"),     {"fields": ("last_seen_visibility", "show_read_receipts", "show_online_status")}),
        (_("Permissions"), {"fields": ("is_active", "is_verified", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Timestamps"),  {"fields": ("created_at", "updated_at")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields":  ("email", "full_name", "password1", "password2"),
        }),
    )


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display  = ["email", "is_used", "attempts", "created_at", "expires_at"]
    list_filter   = ["is_used"]
    search_fields = ["email"]
    readonly_fields = ["id", "created_at"]
    ordering      = ["-created_at"]
