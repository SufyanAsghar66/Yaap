"""Messaging REST Views"""
import logging
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Conversation, Message, MessageTranslation
from .serializers import ConversationSerializer, MessageSerializer, TranslateMessageSerializer

logger = logging.getLogger(__name__)
User = get_user_model()

def _ok(data, sc=status.HTTP_200_OK): return Response({"success": True, "data": data}, status=sc)
def _err(code, msg, sc=status.HTTP_400_BAD_REQUEST): return Response({"success": False, "error": {"code": code, "message": msg}}, status=sc)


class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        convs = Conversation.objects.for_user(request.user)
        return _ok({"conversations": ConversationSerializer(convs, many=True, context={"request": request}).data})

class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        uid = request.data.get("user_id")
        if not uid: return _err("MISSING_USER", "user_id required.")
        try:
            other = User.objects.get(id=uid, is_active=True)
        except User.DoesNotExist:
            return _err("NOT_FOUND", "User not found.", status.HTTP_404_NOT_FOUND)
        if str(other.id) == str(request.user.id): return _err("SELF", "Cannot message yourself.")
        from apps.friendships.models import Friendship
        if not Friendship.objects.are_friends(request.user, other):
            return _err("NOT_FRIENDS", "Must be friends first.", status.HTTP_403_FORBIDDEN)
        conv, created = Conversation.objects.get_or_create_between(request.user, other)
        return _ok({"conversation": ConversationSerializer(conv, context={"request": request}).data},
                   status.HTTP_201_CREATED if created else status.HTTP_200_OK)

class MessageListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, conversation_id):
        try:
            conv = Conversation.objects.get(Q(id=conversation_id) & (Q(participant_a=request.user) | Q(participant_b=request.user)))
        except Conversation.DoesNotExist:
            return _err("NOT_FOUND", "Conversation not found.", status.HTTP_404_NOT_FOUND)
        cursor    = request.query_params.get("cursor")
        page_size = min(int(request.query_params.get("page_size", 50)), 100)
        qs = Message.objects.visible_to(request.user, conv)
        if cursor:
            from django.utils.dateparse import parse_datetime
            try: qs = qs.filter(created_at__lt=parse_datetime(cursor))
            except Exception: pass
        batch     = list(qs[:page_size + 1])
        has_more  = len(batch) > page_size
        batch     = batch[:page_size]
        next_cur  = batch[-1].created_at.isoformat() if has_more and batch else None
        return _ok({"messages": MessageSerializer(batch, many=True, context={"request": request, "preferred_language": request.user.language_preference}).data,
                    "next_cursor": next_cur, "has_more": has_more})

class TranslateMessageView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, message_id):
        s = TranslateMessageSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        lang = s.validated_data["language"]
        try:
            msg = Message.objects.select_related("conversation").get(id=message_id, deleted_for_everyone=False)
        except Message.DoesNotExist:
            return _err("NOT_FOUND", "Message not found.", status.HTTP_404_NOT_FOUND)
        conv = msg.conversation
        if request.user.id not in (conv.participant_a_id, conv.participant_b_id):
            return _err("FORBIDDEN", "Not a participant.", status.HTTP_403_FORBIDDEN)
        existing = MessageTranslation.objects.filter(message=msg, language=lang).first()
        if existing:
            return _ok({"message_id": str(msg.id), "language": lang, "translated_content": existing.translated_content, "cached": True})
        from services.translation import translate
        translated  = translate(msg.content, lang, msg.original_language)
        translation = MessageTranslation.objects.create(message=msg, language=lang, translated_content=translated)
        return _ok({"message_id": str(msg.id), "language": lang, "translated_content": translation.translated_content, "cached": False})

class DeleteMessageView(APIView):
    permission_classes = [IsAuthenticated]
    def delete(self, request, message_id):
        scope = request.data.get("scope", "me")
        if scope not in ("everyone", "me"): return _err("INVALID_SCOPE", "scope: 'everyone' or 'me'.")
        try:
            msg = Message.objects.select_related("conversation").get(id=message_id)
        except Message.DoesNotExist:
            return _err("NOT_FOUND", "Message not found.", status.HTTP_404_NOT_FOUND)
        conv = msg.conversation
        if request.user.id not in (conv.participant_a_id, conv.participant_b_id):
            return _err("FORBIDDEN", "Not a participant.", status.HTTP_403_FORBIDDEN)
        if scope == "everyone":
            if msg.sender_id != request.user.id: return _err("NOT_SENDER", "Only sender can delete for everyone.")
            if not msg.can_delete_for_everyone(request.user): return _err("WINDOW_EXPIRED", "Delete window has passed.")
            msg.delete_for_everyone()
        else:
            msg.delete_for_user(request.user)
        return _ok({"message": f"Deleted for {scope}."})
