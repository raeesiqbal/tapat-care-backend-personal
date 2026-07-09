from datetime import timedelta
from secrets import token_urlsafe

from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application, RefreshToken
from oauth2_provider.settings import oauth2_settings


def issue_oauth_session(user, client_id):
    if not client_id:
        raise ImproperlyConfigured(
            "An OAuth client ID is required to create the verified session."
        )

    application = Application.objects.filter(
        client_id=client_id,
        authorization_grant_type=Application.GRANT_PASSWORD,
    ).first()
    if not application:
        raise ImproperlyConfigured(
            "The OAuth client ID does not match an OAuth application."
        )

    expires_in = oauth2_settings.ACCESS_TOKEN_EXPIRE_SECONDS
    access_token = AccessToken.objects.create(
        user=user,
        application=application,
        token=token_urlsafe(48),
        expires=timezone.now() + timedelta(seconds=expires_in),
        scope="read write",
    )
    refresh_token = RefreshToken.objects.create(
        user=user,
        application=application,
        token=token_urlsafe(48),
        access_token=access_token,
    )

    return {
        "access_token": access_token.token,
        "refresh_token": refresh_token.token,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "scope": access_token.scope,
    }
