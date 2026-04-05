from django.contrib import admin
from .models import Conversation, Message, MessageTranslation, MessageDeletion

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "participant_a", "participant_b", "updated_at"]
    search_fields = ["participant_a__email", "participant_b__email"]

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "sender", "conversation", "status", "deleted_for_everyone", "created_at"]
    list_filter  = ["status", "deleted_for_everyone"]
    search_fields = ["sender__email", "content"]

@admin.register(MessageTranslation)
class MessageTranslationAdmin(admin.ModelAdmin):
    list_display = ["message", "language", "created_at"]
    list_filter  = ["language"]
