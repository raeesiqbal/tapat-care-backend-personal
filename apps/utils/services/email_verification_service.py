import math
import uuid
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.caregivers.models import Caregiver
from apps.careseekers.models import Careseeker
from apps.users.models import User
from apps.utils.services.email_service import send_email_to_user
from apps.utils.services.oauth_token_service import issue_oauth_session


EMAIL_VERIFICATION_SALT = "tapat-care.email-verification"


class EmailVerificationError(Exception):
    code = "email_verification_error"

    def __init__(self, message, *, email=""):
        super().__init__(message)
        self.email = email


class EmailVerificationExpired(EmailVerificationError):
    code = "verification_link_expired"


class EmailVerificationInvalid(EmailVerificationError):
    code = "verification_link_invalid"


class VerificationEmailRecentlySent(EmailVerificationError):
    code = "verification_email_rate_limited"

    def __init__(self, retry_after):
        super().__init__(
            f"Please wait {retry_after} seconds before requesting another email."
        )
        self.retry_after = retry_after


def _token_payload(user, nonce):
    return {
        "user_id": user.pk,
        "email": user.email,
        "nonce": str(nonce),
    }


def _build_verification_url(token):
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    if not frontend_url:
        raise ImproperlyConfigured("FRONTEND_URL is required for verification emails.")
    return f"{frontend_url}/api/onboarding/verify-email?token={quote(token)}"


def send_verification_email(user, *, enforce_cooldown=True):
    if user.is_verified:
        raise EmailVerificationError(
            "This email address is already verified.",
            email=user.email,
        )

    now = timezone.now()
    cooldown = settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS
    if enforce_cooldown and user.email_verification_sent_at:
        elapsed = (now - user.email_verification_sent_at).total_seconds()
        if elapsed < cooldown:
            raise VerificationEmailRecentlySent(math.ceil(cooldown - elapsed))

    previous_nonce = user.email_verification_nonce
    previous_sent_at = user.email_verification_sent_at
    nonce = uuid.uuid4()
    user.email_verification_nonce = nonce
    user.email_verification_sent_at = now
    user.save(
        update_fields=[
            "email_verification_nonce",
            "email_verification_sent_at",
        ]
    )

    token = signing.dumps(
        _token_payload(user, nonce),
        salt=EMAIL_VERIFICATION_SALT,
        compress=True,
    )
    verification_url = _build_verification_url(token)
    expiration_hours = max(
        1,
        math.ceil(settings.EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS / 3600),
    )
    context = {
        "full_name": user.get_full_name().strip() or "there",
        "verification_url": verification_url,
        "expiration_hours": expiration_hours,
        "current_year": now.year,
    }

    try:
        send_email_to_user(
            "Verify your Tapat Care email",
            render_to_string("emails/verify_account/verify-account.html", context),
            render_to_string("emails/verify_account/verify-account.txt", context),
            settings.DEFAULT_FROM_EMAIL,
            user.email,
        )
    except Exception:
        user.email_verification_nonce = previous_nonce
        user.email_verification_sent_at = previous_sent_at
        user.save(
            update_fields=[
                "email_verification_nonce",
                "email_verification_sent_at",
            ]
        )
        raise


def _load_token(token, *, max_age):
    return signing.loads(
        token,
        salt=EMAIL_VERIFICATION_SALT,
        max_age=max_age,
    )


def _expired_token_email(token):
    try:
        payload = _load_token(token, max_age=None)
    except signing.BadSignature:
        return ""
    return str(payload.get("email") or "").strip().lower()


def _mark_email_verification_complete(profile):
    raw = (
        profile.onboarding_resume
        if isinstance(getattr(profile, "onboarding_resume", None), dict)
        else {}
    )
    completed_steps = [
        step
        for step in raw.get("completed_steps", [])
        if step in {"account", "verification"}
    ]
    for step in ("account", "verification"):
        if step not in completed_steps:
            completed_steps.append(step)
    profile.onboarding_resume = {
        **raw,
        "status": "in_progress",
        "completed_steps": completed_steps,
        "next_step": "personal-details",
    }
    profile.save(update_fields=["onboarding_resume", "updated_at"])


@transaction.atomic
def verify_email_and_issue_session(token, client_id):
    try:
        payload = _load_token(
            token,
            max_age=settings.EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired as exc:
        raise EmailVerificationExpired(
            "This verification link has expired.",
            email=_expired_token_email(token),
        ) from exc
    except signing.BadSignature as exc:
        raise EmailVerificationInvalid(
            "This verification link is invalid."
        ) from exc

    user_id = payload.get("user_id")
    email = str(payload.get("email") or "").strip().lower()
    nonce = str(payload.get("nonce") or "")
    user = User.objects.select_for_update().filter(pk=user_id).first()

    if (
        user
        and user.email.lower() == email
        and user.is_verified
        and user.email_verification_nonce
        and str(user.email_verification_nonce) == nonce
    ):
        return user, issue_oauth_session(user, client_id), "already_verified"

    if (
        not user
        or user.email.lower() != email
        or not user.email_verification_nonce
        or str(user.email_verification_nonce) != nonce
    ):
        raise EmailVerificationInvalid(
            "This verification link is invalid or has already been used.",
            email=email,
        )

    user.is_verified = True
    user.save(update_fields=["is_verified"])

    caregiver = Caregiver.objects.select_for_update().filter(user=user).first()
    if caregiver:
        _mark_email_verification_complete(caregiver)

    careseeker = (
        Careseeker.objects.select_for_update()
        .filter(careseeker_user=user)
        .first()
    )
    if careseeker:
        _mark_email_verification_complete(careseeker)

    return user, issue_oauth_session(user, client_id), "verified"
