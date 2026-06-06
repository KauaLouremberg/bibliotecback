from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User


@database_sync_to_async
def _user_from_token(token: str | None):
    if not token:
        return AnonymousUser()
    try:
        access = AccessToken(token)
        user_id = access.get("user_id")
    except (TokenError, InvalidToken, KeyError):
        return AnonymousUser()
    if user_id is None:
        return AnonymousUser()
    try:
        return User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get("token", [None])[0]
        scope["user"] = await _user_from_token(token)
        return await super().__call__(scope, receive, send)
