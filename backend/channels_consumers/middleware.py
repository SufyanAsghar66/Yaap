"""
JWT Authentication Middleware for Django Channels WebSocket connections.

The Kotlin client sends the JWT access token as a query parameter:
  ws://host/ws/chat/123/?token=<access_token>

This middleware validates the token and attaches the user to scope
before passing control to the consumer. Unauthenticated connections
are closed immediately with code 4001.
"""

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)
User   = get_user_model()


@database_sync_to_async
def _get_user_from_token(token_str: str):
    """Validate JWT and return the associated User, or None."""
    try:
        token   = AccessToken(token_str)
        user_id = token.get("user_id")
        if not user_id:
            return None
        return User.objects.select_related().get(id=user_id, is_active=True)
    except (InvalidToken, TokenError) as e:
        logger.warning("WebSocket JWT validation failed: %s", e)
        return None
    except User.DoesNotExist:
        logger.warning("WebSocket JWT references non-existent user_id=%s", token.get("user_id"))
        return None
    except Exception as e:
        logger.error("Unexpected error in WebSocket JWT middleware: %s", e)
        return None


class JWTAuthMiddleware(BaseMiddleware):
    """
    Middleware that authenticates WebSocket connections via JWT query param.
    Sets scope["user"] to the User instance or AnonymousUser.
    """

    async def __call__(self, scope, receive, send):
        # Extract token from query string: ?token=<jwt>
        query_string = scope.get("query_string", b"").decode("utf-8")
        params       = parse_qs(query_string)
        token_list   = params.get("token", [])

        if token_list:
            token  = token_list[0]
            user   = await _get_user_from_token(token)
            scope["user"] = user or AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        if isinstance(scope["user"], AnonymousUser):
            logger.warning(
                "Unauthenticated WebSocket connection rejected: path=%s",
                scope.get("path", "unknown"),
            )
            # Close the connection with 4001 (unauthorized)
            await send({"type": "websocket.close", "code": 4001})
            return

        await super().__call__(scope, receive, send)
