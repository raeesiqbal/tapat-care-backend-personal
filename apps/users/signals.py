from datetime import date
from apps.utils.services.email_service import send_email_to_user
from django_rest_passwordreset.signals import (
    post_password_reset,
    reset_password_token_created,
)

from django.conf import settings
from django.dispatch import receiver
from django.template.loader import render_to_string


@receiver(reset_password_token_created)
def password_reset_token_created(
    sender, instance, reset_password_token, *args, **kwargs
):
    user = reset_password_token.user

    url = settings.FRONTEND_URL

    context = {
        "full_name": "{} {}".format(user.first_name.title(), user.last_name.title()),
        "year": date.today().year,
        "reset_password_url": "{}/reset-password?token={}".format(
            url, reset_password_token.key
        ),
    }

    send_email_to_user(
        "Reset Your Password",
        render_to_string("emails/reset_password/user_reset_password.html", context),
        render_to_string("emails/reset_password/user_reset_password.txt", context),
        settings.EMAIL_HOST_USER,
        user.email,
    )


@receiver(post_password_reset)
def password_reset_successful(sender, user, *args, **kwargs):
    """
    Handles successful password reset email.
    """
    context = {
        "full_name": "{} {}".format(user.first_name.title(), user.last_name.title()),
        "year": date.today().year,
    }

    send_email_to_user(
        "Password Updated Successfully",
        render_to_string(
            "emails/reset_password/reset-password-successful.html", context
        ),
        render_to_string(
            "emails/reset_password/reset-password-successful.txt", context
        ),
        settings.EMAIL_HOST_USER,
        user.email,
    )
