from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template.loader import render_to_string
from django.utils import timezone

from apps.utils.services.email_service import send_email_to_user


def _build_frontend_url(path: str) -> str:
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    if not frontend_url:
        raise ImproperlyConfigured("FRONTEND_URL is required for account status emails.")
    return f"{frontend_url}{path}"


def _send_account_status_email(
    *,
    subject: str,
    user,
    heading: str,
    message: str,
    button_text: str,
    button_url: str,
) -> None:
    context = {
        "full_name": user.get_full_name().strip() or "there",
        "heading": heading,
        "message": message,
        "button_text": button_text,
        "button_url": button_url,
        "current_year": timezone.now().year,
    }
    send_email_to_user(
        subject,
        render_to_string("emails/account_status.html", context),
        render_to_string("emails/account_status.txt", context),
        settings.DEFAULT_FROM_EMAIL,
        user.email,
    )


def send_careseeker_welcome_email(careseeker) -> None:
    _send_account_status_email(
        subject="Your Tapat Care account is ready",
        user=careseeker.careseeker_user,
        heading="Your account is ready",
        message=(
            "Your careseeker account is ready. You can now browse caregiver profiles. "
            "A subscription is required to send messages to caregivers or receive "
            "messages from them."
        ),
        button_text="Go to dashboard",
        button_url=_build_frontend_url("/dashboard"),
    )


def send_caregiver_approved_email(caregiver) -> None:
    _send_account_status_email(
        subject="Your Tapat Care account is approved",
        user=caregiver.user,
        heading="Your account is approved",
        message=(
            "Your caregiver account is approved, and your safety screening is also "
            "approved. Dashboard access is now available."
        ),
        button_text="Go to dashboard",
        button_url=_build_frontend_url("/dashboard"),
    )


def send_caregiver_rejected_email(caregiver) -> None:
    _send_account_status_email(
        subject="Update on your Tapat Care application",
        user=caregiver.user,
        heading="Your application was not approved",
        message=(
            "Your caregiver account was not approved, and your safety screening was "
            "not approved. Dashboard access remains unavailable."
        ),
        button_text="Back to Tapat Care",
        button_url=_build_frontend_url("/"),
    )
