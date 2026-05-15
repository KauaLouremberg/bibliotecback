from ninja.security import HttpBearer
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .models import User


class JwtAuth(HttpBearer):
    def authenticate(self, request, token: str) -> User | None:
        try:
            access = AccessToken(token)
            user_id = access.get("user_id")
        except (TokenError, InvalidToken, KeyError):
            return None
        if user_id is None:
            return None
        try:
            return User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return None
