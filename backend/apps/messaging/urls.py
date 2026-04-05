from django.urls import path
from .views import ConversationListView, ConversationDetailView, MessageListView, TranslateMessageView, DeleteMessageView

urlpatterns = [
    path("",                                          ConversationListView.as_view(),   name="conversation-list"),
    path("start/",                                    ConversationDetailView.as_view(),  name="conversation-start"),
    path("<uuid:conversation_id>/messages/",          MessageListView.as_view(),         name="message-list"),
    path("messages/<uuid:message_id>/translate/",     TranslateMessageView.as_view(),    name="message-translate"),
    path("messages/<uuid:message_id>/",               DeleteMessageView.as_view(),        name="message-delete"),
]
