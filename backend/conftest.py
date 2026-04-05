"""Global pytest conftest — shared fixtures for all phases 1-7."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

def make_user(email="test@yaap.app", password="TestPass123!", full_name="Test User",
              display_name="TestUser", language_preference="en", is_verified=True, **kwargs):
    return User.objects.create_user(
        email=email, password=password, full_name=full_name, display_name=display_name,
        language_preference=language_preference, is_verified=is_verified, **kwargs,
    )

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user(db):
    return make_user()

@pytest.fixture
def user_b(db):
    return make_user(email="user_b@yaap.app", display_name="UserB", language_preference="ar")

@pytest.fixture
def user_c(db):
    return make_user(email="user_c@yaap.app", display_name="UserC", language_preference="fr")

@pytest.fixture
def auth_client(db, user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client, user

@pytest.fixture
def auth_client_b(db, user_b):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user_b).access_token}")
    return client, user_b

@pytest.fixture
def auth_client_c(db, user_c):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user_c).access_token}")
    return client, user_c

@pytest.fixture
def friends(db, user, user_b):
    from apps.friendships.models import FriendRequest
    FriendRequest.objects.create(from_user=user, to_user=user_b).accept()
    return user, user_b

@pytest.fixture
def voice_sentences(db):
    from apps.voice.models import VoiceSentence
    return [VoiceSentence.objects.create(language="en", sentence=f"Test sentence {i}.", position=i) for i in range(1,6)]

@pytest.fixture
def conversation(db, friends):
    from apps.messaging.models import Conversation
    conv, _ = Conversation.objects.get_or_create_between(*friends)
    return conv

@pytest.fixture
def call_room(db, friends):
    from apps.calls.models import CallRoom
    user, user_b = friends
    return CallRoom.objects.create(caller=user, callee=user_b, caller_language="en", callee_language="ar")
