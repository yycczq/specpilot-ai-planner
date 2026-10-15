from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed


class ExpiringTokenAuthentication(TokenAuthentication):
    """Expire API tokens after the configured lifetime and remove stale credentials."""

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        lifetime = timedelta(days=settings.API_TOKEN_TTL_DAYS)
        if token.created <= timezone.now() - lifetime:
            token.delete()
            raise AuthenticationFailed("API Token 已过期，请重新登录。")
        return user, token


def get_or_issue_token(user):
    """Return the user's active token, replacing it if its lifetime has elapsed."""
    token = Token.objects.filter(user=user).first()
    if token is not None and token.created <= timezone.now() - timedelta(days=settings.API_TOKEN_TTL_DAYS):
        token.delete()
        token = None
    if token is None:
        token = Token.objects.create(user=user)
    return token
