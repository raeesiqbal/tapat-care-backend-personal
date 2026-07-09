import math
import secrets
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone


class PhoneVerificationError(Exception):
    code = "phone_verification_error"

    def __init__(self, message, *, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class PhoneVerificationRateLimited(PhoneVerificationError):
    code = "phone_verification_rate_limited"


class PhoneVerificationInvalidCode(PhoneVerificationError):
    code = "phone_verification_invalid_code"


class PhoneVerificationExpired(PhoneVerificationError):
    code = "phone_verification_code_expired"


class PhoneVerificationUnavailable(PhoneVerificationError):
    code = "phone_verification_unavailable"


DEVELOPMENT_PHONE_VERIFICATION_CODE_TTL_SECONDS = 10 * 60


def normalize_phone_number(phone: str) -> str:
    raw = str(phone or "").strip()
    if not raw:
        raise PhoneVerificationError("Phone number is required.")

    digits = "".join(ch for ch in raw if ch.isdigit())
    if raw.startswith("+"):
        normalized = f"+{digits}"
    elif len(digits) == 10:
        normalized = f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        normalized = f"+{digits}"
    else:
        raise PhoneVerificationError("Enter a valid US phone number.")

    if len(normalized) < 12 or len(normalized) > 16:
        raise PhoneVerificationError("Enter a valid US phone number.")

    return normalized


def mask_phone_number(phone: str) -> str:
    normalized = normalize_phone_number(phone)
    return f"{normalized[:-4].replace(normalized[1:-4], '***-***-')}{normalized[-4:]}"


def _get_verify_endpoint(path: str) -> str:
    account_sid = settings.TWILIO_ACCOUNT_SID.strip()
    base_url = f"https://verify.twilio.com/v2/Services/{settings.TWILIO_VERIFY_SERVICE_SID.strip()}/"
    if not account_sid or not settings.TWILIO_AUTH_TOKEN.strip() or not settings.TWILIO_VERIFY_SERVICE_SID.strip():
        raise ImproperlyConfigured("Twilio Verify credentials are not configured.")
    return urljoin(base_url, path)


def _get_phone_verification_mode() -> str:
    mode = str(getattr(settings, "PHONE_VERIFICATION_MODE", "production")).strip().lower()
    if mode not in {"development", "production"}:
        raise ImproperlyConfigured(
            "PHONE_VERIFICATION_MODE must be either 'development' or 'production'."
        )
    return mode


def _build_development_cache_key(user_id: int, phone: str) -> str:
    return f"phone-verification:{user_id}:{phone}"


def _generate_development_verification_code() -> str:
    demo_code = _get_development_demo_code()
    if demo_code:
        return demo_code
    return f"{secrets.randbelow(1_000_000):06d}"


def _get_development_demo_code() -> str:
    return str(getattr(settings, "PHONE_VERIFICATION_DEVELOPMENT_CODE", "123456")).strip()


def _store_development_verification_code(user_id: int, phone: str, code: str) -> None:
    cache.set(
        _build_development_cache_key(user_id, phone),
        code,
        timeout=DEVELOPMENT_PHONE_VERIFICATION_CODE_TTL_SECONDS,
    )


def _get_stored_development_verification_code(user_id: int, phone: str) -> str | None:
    cached_code = cache.get(_build_development_cache_key(user_id, phone))
    return str(cached_code) if cached_code is not None else None


def _clear_stored_development_verification_code(user_id: int, phone: str) -> None:
    cache.delete(_build_development_cache_key(user_id, phone))


def clear_phone_verification_state(user, phone: str | None) -> None:
    normalized_phone = str(phone or "").strip()
    if not normalized_phone:
        return

    if _get_phone_verification_mode() == "development":
        _clear_stored_development_verification_code(user.pk, normalized_phone)


def _send_development_phone_verification(user, normalized_phone: str) -> dict[str, str | int]:
    code = _generate_development_verification_code()
    _store_development_verification_code(user.pk, normalized_phone, code)
    print("=====================================")
    print("DEVELOPMENT PHONE VERIFICATION")
    print(f"Phone: {normalized_phone}")
    print(f"Code: {code}")
    print("=====================================")
    return {
        "phone": normalized_phone,
        "masked_phone": mask_phone_number(normalized_phone),
        "status": "pending",
        "retry_after": settings.PHONE_VERIFICATION_RESEND_COOLDOWN_SECONDS,
    }


def _check_development_phone_verification(user, normalized_phone: str, code: str) -> dict[str, str]:
    demo_code = _get_development_demo_code()
    if demo_code and code == demo_code:
        _clear_stored_development_verification_code(user.pk, normalized_phone)
        return {
            "phone": normalized_phone,
            "status": "approved",
        }

    stored_code = _get_stored_development_verification_code(user.pk, normalized_phone)
    if not stored_code:
        raise PhoneVerificationExpired("This verification code has expired.")
    if stored_code != code:
        raise PhoneVerificationInvalidCode("The verification code is incorrect.")

    _clear_stored_development_verification_code(user.pk, normalized_phone)
    return {
        "phone": normalized_phone,
        "status": "approved",
    }


def _request_verify(path: str, data: dict[str, str]):
    endpoint = _get_verify_endpoint(path)
    response = requests.post(
        endpoint,
        data=data,
        auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        timeout=10,
    )

    if response.status_code == 429:
        raise PhoneVerificationRateLimited(
            "Please wait before requesting another verification code.",
            retry_after=settings.PHONE_VERIFICATION_RESEND_COOLDOWN_SECONDS,
        )

    payload = response.json() if response.content else {}
    if not response.ok:
        message = str(payload.get("message") or "Phone verification is unavailable.")
        raise PhoneVerificationUnavailable(message)

    return payload


def send_phone_verification(user, phone: str) -> dict[str, str | int]:
    normalized_phone = normalize_phone_number(phone)
    cooldown = settings.PHONE_VERIFICATION_RESEND_COOLDOWN_SECONDS
    now = timezone.now()

    if user.phone_verification_sent_at:
        elapsed = (now - user.phone_verification_sent_at).total_seconds()
        if elapsed < cooldown:
            raise PhoneVerificationRateLimited(
                f"Please wait {math.ceil(cooldown - elapsed)} seconds before requesting another code.",
                retry_after=math.ceil(cooldown - elapsed),
            )

    # Development mode is an explicit local-only fallback that never talks to
    # Twilio. Production keeps the existing Verify API flow unchanged.
    if _get_phone_verification_mode() == "development":
        payload = _send_development_phone_verification(user, normalized_phone)
    else:
        payload = _request_verify(
            "Verifications",
            {
                "To": normalized_phone,
                "Channel": "sms",
            },
        )

    user.phone = normalized_phone
    user.phone_verification_sent_at = now
    user.save(update_fields=["phone", "phone_verification_sent_at"])

    return {
        "phone": normalized_phone,
        "masked_phone": mask_phone_number(normalized_phone),
        "status": str(payload.get("status") or "pending"),
        "retry_after": cooldown,
    }


def check_phone_verification(user, phone: str, code: str) -> dict[str, str]:
    normalized_phone = normalize_phone_number(phone)
    normalized_code = str(code or "").strip()

    if not normalized_code:
        raise PhoneVerificationError("Verification code is required.")

    if _get_phone_verification_mode() == "development":
        payload = _check_development_phone_verification(
            user,
            normalized_phone,
            normalized_code,
        )
    else:
        payload = _request_verify(
            "VerificationCheck",
            {
                "To": normalized_phone,
                "Code": normalized_code,
            },
        )

    status = str(payload.get("status") or "").strip().lower()
    if status == "approved":
        return {
            "phone": normalized_phone,
            "status": "approved",
        }
    if status == "pending":
        raise PhoneVerificationInvalidCode("The verification code is incorrect.")
    if status == "expired":
        raise PhoneVerificationExpired("This verification code has expired.")

    raise PhoneVerificationUnavailable("Phone verification is unavailable.")
