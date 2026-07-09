import base64
import datetime
import logging
from django.conf import settings
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from apps.utils.views.base import BaseViewset, ResponseInfo
from rest_framework.permissions import IsAuthenticated
from tapat_care.settings import SECRET_KEY
import jwt
from drf_yasg.utils import swagger_auto_schema
from drf_social_oauth2.views import TokenView as SocialTokenView
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from oauth2_provider.models import AccessToken, RefreshToken
from apps.utils.services.zipcode_service import get_us_zip_details
from apps.utils.services.email_service import send_email_to_user
from apps.utils.services.email_verification_service import (
    EmailVerificationError,
    EmailVerificationExpired,
    EmailVerificationInvalid,
    VerificationEmailRecentlySent,
    send_verification_email,
    verify_email_and_issue_session,
)
from apps.utils.services.phone_verification_service import (
    PhoneVerificationError,
    PhoneVerificationExpired,
    PhoneVerificationInvalidCode,
    PhoneVerificationRateLimited,
    check_phone_verification,
    clear_phone_verification_state,
    mask_phone_number,
    normalize_phone_number,
    send_phone_verification,
)
from apps.users.permissions import IsEmailVerified

# permissions

# serializers
from apps.users.serializers import (
    RegisterUserSerializer,
    GetUserSerializer,
    OAuthTokenRequestSerializer,
    RegisterCaregiverSerializer,
    RegisterCareseekerSerializer,
    UpdatePasswordSerializer,
    UserPictureSerializer,
)


# models
from apps.users.models import User, Role, UserRole
from apps.caregivers.models import Caregiver
from apps.careseekers.models import Careseeker

# Create your views here.

logger = logging.getLogger(__name__)


def _get_user_display_name(user):
    full_name = str(user.get_full_name() or "").strip()

    if full_name:
        return full_name

    if user.first_name:
        return user.first_name

    return user.email


def _describe_user_agent(user_agent):
    normalized = str(user_agent or "").lower()

    if "edg/" in normalized:
        browser = "Edge"
    elif "chrome/" in normalized and "chromium" not in normalized:
        browser = "Chrome"
    elif "firefox/" in normalized:
        browser = "Firefox"
    elif "safari/" in normalized:
        browser = "Safari"
    else:
        browser = "Unknown browser"

    if "windows" in normalized:
        platform = "Windows"
    elif "mac os x" in normalized or "macintosh" in normalized:
        platform = "macOS"
    elif "iphone" in normalized or "ipad" in normalized:
        platform = "iOS"
    elif "android" in normalized:
        platform = "Android"
    elif "linux" in normalized:
        platform = "Linux"
    else:
        platform = "Unknown device"

    if browser == "Unknown browser" and platform == "Unknown device":
        return "Unknown device"

    return f"{browser} on {platform}"


def _send_password_changed_email(user, changed_at, device):
    changed_at_utc = changed_at.astimezone(datetime.timezone.utc)
    context = {
        "user_name": _get_user_display_name(user),
        "changed_date": (
            f"{changed_at_utc.strftime('%B')} {changed_at_utc.day}, "
            f"{changed_at_utc.year}"
        ),
        "changed_time": (
            f"{changed_at_utc.strftime('%I').lstrip('0')}:"
            f"{changed_at_utc.strftime('%M %p')} UTC"
        ),
        "device": device,
    }
    html_message = render_to_string(
        "emails/security/password-changed.html",
        context,
    )
    plaintext_message = render_to_string(
        "emails/security/password-changed.txt",
        context,
    )

    send_email_to_user(
        "Your Tapat Care password was changed",
        html_message,
        plaintext_message,
        getattr(settings, "DEFAULT_FROM_EMAIL", None),
        user.email,
    )


def _advance_onboarding_after_phone_verification(profile):
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

    next_step = str(raw.get("next_step") or "").strip() or "personal-details"
    if next_step == "verification":
        next_step = "personal-details"

    profile.onboarding_resume = {
        **raw,
        "status": "in_progress",
        "completed_steps": completed_steps,
        "next_step": next_step,
    }
    profile.save(update_fields=["onboarding_resume", "updated_at"])
    return next_step


class OAuthTokenView(SocialTokenView):
    @swagger_auto_schema(
        operation_summary="Generate OAuth token",
        request_body=OAuthTokenRequestSerializer,
        responses={200: "Token response", 400: "Invalid request"},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class UserViewSet(BaseViewset):
    queryset = User.objects.all()
    action_serializers = {
        "default": GetUserSerializer,
        "register": RegisterUserSerializer,
        "register_caregiver": RegisterCaregiverSerializer,
        "register_careseeker": RegisterCareseekerSerializer,
        "update_password": UpdatePasswordSerializer,
        "picture": UserPictureSerializer,
    }
    action_permissions = {
        "default": [IsAuthenticated],
        "register": [],
        "register_caregiver": [],
        "register_careseeker": [],
        "email_availability": [],
        "zip_details": [],
        "verify_email": [],
        "resend_email_verification": [],
        "reset_phone_verification": [IsAuthenticated, IsEmailVerified],
        "send_phone_verification": [IsAuthenticated, IsEmailVerified],
        "verify_phone": [IsAuthenticated, IsEmailVerified],
    }

    @action(detail=False, url_path="register", methods=["post"])
    def register(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            status=status.HTTP_201_CREATED,
            data=ResponseInfo().format_response(
                data={},
                status_code=status.HTTP_201_CREATED,
                message=f"Welcome {user.email}, please login to your account.",
            ),
        )
        
    # def create(self, request, *args, **kwargs):
    #     serializer = self.get_serializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)

    #     user = User.objects.create(**serializer.validated_data)
    #     # Setting password.
    #     user.set_password(serializer.validated_data.get("password"))
    #     # Granting super user access

    #     return Response(
    #         status=status.HTTP_201_CREATED,
    #         data=ResponseInfo().format_response(
    #             data={},
    #             status_code=status.HTTP_201_CREATED,
    #             message=f"Welcome {user.email}, please login to your account.",
    #         ),
    #     )

    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data.get("password", None)
        if password:
            # Assuming 'instance' has a reference to the user
            # Set the password for the user
            user = instance
            instance.set_password(password)
            # Save the user object to persist the password change
            user.save()
        self.perform_update(serializer)
        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data=serializer.data,
                status_code=status.HTTP_200_OK,
                message="User is updated",
            ),
        )
    @action(detail=False, url_path="validate-user", methods=["post"])
    def validate_user(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data.get("password", None)

        user = request.user
        if not user.check_password(password):
            return Response(
                status=status.HTTP_403_FORBIDDEN,
                data=ResponseInfo().format_response(
                    data={},
                    message="Passowrd incorrect",
                    status_code=status.HTTP_403_FORBIDDEN,
                ),
            )

        token = jwt.encode(
            {
                "id": user.id,
                "exp": datetime.datetime.now(tz=datetime.timezone.utc)
                + datetime.timedelta(minutes=20),
            },
            SECRET_KEY,
            algorithm="HS256",
        )

        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data={"token": token},
                message="token generated",
                status_code=status.HTTP_200_OK,
            ),
        )

    @action(detail=False, url_path="me", methods=["get"])
    def get_me(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.user, many=False)

        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data=serializer.data,
                message="Me",
                status_code=status.HTTP_200_OK,
            ),
        )

    @action(
        detail=False,
        url_path="picture",
        methods=["patch"],
        parser_classes=[MultiPartParser, FormParser],
    )
    def picture(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data=serializer.errors,
                    message="Please choose a valid profile photo.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                ),
            )

        upload = serializer.validated_data["file"]
        content_type = serializer.validated_data["content_type"]
        encoded_file = base64.b64encode(upload.read()).decode("ascii")
        request.user.picture = f"data:{content_type};base64,{encoded_file}"
        request.user.save(update_fields=["picture"])

        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data={"picture": request.user.picture},
                message="Profile photo updated.",
                status_code=status.HTTP_200_OK,
            ),
        )

    @action(detail=False, url_path="send-phone-verification", methods=["post"])
    def send_phone_verification(self, request, *args, **kwargs):
        requested_phone = str(request.data.get("phone", "")).strip()
        phone = requested_phone or str(request.user.phone or "").strip()

        if not phone:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={"code": "phone_required"},
                    message="Phone number is required.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                ),
            )

        try:
            normalized_phone = normalize_phone_number(phone)
            if (
                request.user.phone_verified_at
                and request.user.phone
                and normalized_phone != request.user.phone
            ):
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data=ResponseInfo().format_response(
                        data={"code": "phone_change_confirmation_required"},
                        message="Confirm the phone number change before sending a new verification code.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    ),
                )
            if normalized_phone != request.user.phone:
                request.user.phone = normalized_phone
                request.user.phone_verified_at = None
                request.user.save(update_fields=["phone", "phone_verified_at"])

            result = send_phone_verification(request.user, normalized_phone)
        except PhoneVerificationRateLimited as exc:
            masked_phone = mask_phone_number(phone)
            return Response(
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                data=ResponseInfo().format_response(
                    data={
                        "code": exc.code,
                        "retry_after": exc.retry_after,
                        "phone": str(request.user.phone or normalized_phone),
                        "masked_phone": masked_phone,
                    },
                    message=str(exc),
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                ),
            )
        except PhoneVerificationError as exc:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={"code": exc.code},
                    message=str(exc),
                    status_code=status.HTTP_400_BAD_REQUEST,
                ),
            )
        except Exception:
            logger.exception(
                "Could not send phone verification for user %s.",
                request.user.pk,
            )
            return Response(
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
                data=ResponseInfo().format_response(
                    data={"code": "phone_verification_unavailable"},
                    message="Phone verification is temporarily unavailable.",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                ),
            )

        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data={
                    "phone": result["phone"],
                    "masked_phone": result["masked_phone"],
                    "retry_after": result["retry_after"],
                    "phone_verified": False,
                },
                message="Verification code sent successfully.",
                status_code=status.HTTP_200_OK,
            ),
        )

    @action(detail=False, url_path="reset-phone-verification", methods=["post"])
    def reset_phone_verification(self, request, *args, **kwargs):
        old_phone = str(request.user.phone or "").strip()
        clear_phone_verification_state(request.user, old_phone)
        request.user.phone = ""
        request.user.phone_verified_at = None
        request.user.phone_verification_sent_at = None
        request.user.save(
            update_fields=["phone", "phone_verified_at", "phone_verification_sent_at"]
        )

        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data={
                    "phone": "",
                    "phone_verified": False,
                },
                message="Verified phone number unlinked. Enter a new phone number to continue.",
                status_code=status.HTTP_200_OK,
            ),
        )

    @action(detail=False, url_path="verify-phone", methods=["post"])
    def verify_phone(self, request, *args, **kwargs):
        phone = str(request.data.get("phone", "")).strip() or str(request.user.phone or "").strip()
        code = str(request.data.get("code", "")).strip()

        if not phone:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={"code": "phone_required"},
                    message="Phone number is required.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                ),
            )

        if not code:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={"code": "verification_code_required"},
                    message="Verification code is required.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                ),
            )

        try:
            normalized_phone = normalize_phone_number(phone)
            if normalized_phone != request.user.phone:
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data=ResponseInfo().format_response(
                        data={"code": "phone_mismatch"},
                        message="Use the phone number saved on your account.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    ),
                )

            check_phone_verification(request.user, normalized_phone, code)
            request.user.phone_verified_at = timezone.now()
            request.user.phone_verification_sent_at = None
            request.user.save(
                update_fields=["phone_verified_at", "phone_verification_sent_at"]
            )

            next_step = "personal-details"
            caregiver = Caregiver.objects.filter(user=request.user).first()
            if caregiver:
                next_step = _advance_onboarding_after_phone_verification(caregiver)

            careseeker = Careseeker.objects.filter(careseeker_user=request.user).first()
            if careseeker:
                next_step = _advance_onboarding_after_phone_verification(careseeker)
        except PhoneVerificationInvalidCode as exc:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={"code": exc.code},
                    message=str(exc),
                    status_code=status.HTTP_400_BAD_REQUEST,
                ),
            )
        except PhoneVerificationExpired as exc:
            return Response(
                status=status.HTTP_410_GONE,
                data=ResponseInfo().format_response(
                    data={"code": exc.code},
                    message=str(exc),
                    status_code=status.HTTP_410_GONE,
                ),
            )
        except PhoneVerificationRateLimited as exc:
            return Response(
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                data=ResponseInfo().format_response(
                    data={"code": exc.code, "retry_after": exc.retry_after},
                    message=str(exc),
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                ),
            )
        except PhoneVerificationError as exc:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={"code": exc.code},
                    message=str(exc),
                    status_code=status.HTTP_400_BAD_REQUEST,
                ),
            )
        except Exception:
            logger.exception(
                "Could not verify phone code for user %s.",
                request.user.pk,
            )
            return Response(
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
                data=ResponseInfo().format_response(
                    data={"code": "phone_verification_unavailable"},
                    message="Phone verification is temporarily unavailable.",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                ),
            )

        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data={
                    "phone": request.user.phone,
                    "phone_verified": True,
                    "next_step": next_step,
                },
                message="Phone verified successfully.",
                status_code=status.HTTP_200_OK,
            ),
        )

    @action(detail=False, url_path="email-availability", methods=["post"])
    def email_availability(self, request, *args, **kwargs):
        email = str(request.data.get("email", "")).strip().lower()

        if not email:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={"available": False, "exists": False},
                    message="Email is required.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                ),
            )

        user = User.objects.filter(email__iexact=email).first()
        exists = user is not None
        can_resume_onboarding = bool(
            user
            and (
                Caregiver.objects.filter(user=user).exists()
                or Careseeker.objects.filter(careseeker_user=user).exists()
            )
        )

        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data={
                    "available": not exists,
                    "exists": exists,
                    "is_verified": bool(user and user.is_verified),
                    "can_resume_onboarding": can_resume_onboarding,
                },
                message="Email availability checked.",
                status_code=status.HTTP_200_OK,
            ),
        )

    @action(detail=False, url_path="zip-details", methods=["post"])
    def zip_details(self, request, *args, **kwargs):
        zip_code = str(request.data.get("zip", "")).strip()

        if not zip_code:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={},
                    message="ZIP code is required.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                ),
            )

        try:
            details = get_us_zip_details(zip_code)
        except ValueError as exc:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={},
                    message=str(exc),
                    status_code=status.HTTP_400_BAD_REQUEST,
                ),
            )
        except LookupError as exc:
            return Response(
                status=status.HTTP_404_NOT_FOUND,
                data=ResponseInfo().format_response(
                    data={},
                    message=str(exc),
                    status_code=status.HTTP_404_NOT_FOUND,
                ),
            )

        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data={
                    "zip": details["zip_code"],
                    "city": details["city"],
                    "state": details["state"],
                    "location": details["formatted"],
                },
                message=details["formatted"],
                status_code=status.HTTP_200_OK,
            ),
        )

    @action(detail=False, url_path="register-caregiver", methods=["post"])
    def register_caregiver(self, request, *args, **kwargs):
        email = str(request.data.get("email", "")).strip().lower()
        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            return Response(
                status=status.HTTP_409_CONFLICT,
                data=ResponseInfo().format_response(
                    data={
                        "code": "account_exists",
                        "email": existing_user.email,
                        "is_verified": existing_user.is_verified,
                        "can_resume_onboarding": (
                            Caregiver.objects.filter(user=existing_user).exists()
                            or Careseeker.objects.filter(
                                careseeker_user=existing_user
                            ).exists()
                        ),
                    },
                    status_code=status.HTTP_409_CONFLICT,
                    message=(
                        "An account already exists for this email. Log in to "
                        "resume onboarding or use another email."
                    ),
                ),
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        Caregiver.objects.create(
            user=user,
            onboarding_resume={
                "status": "in_progress",
                "completed_steps": ["account"],
                "next_step": "verification",
            },
        )

        caregiver_role = Role.objects.filter(code="caregiver").first()
        if caregiver_role:
            UserRole.objects.get_or_create(user=user, role=caregiver_role)

        verification_email_sent = True
        try:
            send_verification_email(user, enforce_cooldown=False)
        except Exception:
            verification_email_sent = False
            logger.exception(
                "Could not send caregiver verification email to user %s.",
                user.pk,
            )

        return Response(
            status=status.HTTP_201_CREATED,
            data=ResponseInfo().format_response(
                data={
                    "email": user.email,
                    "verification_required": True,
                    "verification_email_sent": verification_email_sent,
                },
                status_code=status.HTTP_201_CREATED,
                message=(
                    "Account created. Check your email to verify your address "
                    "before continuing."
                    if verification_email_sent
                    else (
                        "Account created, but the verification email could not be "
                        "sent. Request another email to continue."
                    )
                ),
            ),
        )

    @action(detail=False, url_path="verify-email", methods=["post"])
    def verify_email(self, request, *args, **kwargs):
        token = str(request.data.get("token", "")).strip()
        client_id = str(request.data.get("client_id", "")).strip()
        if not token or not client_id:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={"code": "verification_link_invalid"},
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="Verification token and OAuth client ID are required.",
                ),
            )

        try:
            user, oauth_session, verification_status = verify_email_and_issue_session(token, client_id)
        except EmailVerificationExpired as exc:
            return Response(
                status=status.HTTP_410_GONE,
                data=ResponseInfo().format_response(
                    data={"code": exc.code, "email": exc.email},
                    status_code=status.HTTP_410_GONE,
                    message=str(exc),
                ),
            )
        except EmailVerificationInvalid as exc:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={"code": exc.code, "email": exc.email},
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message=str(exc),
                ),
            )
        except Exception:
            logger.exception("Could not verify email token.")
            return Response(
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
                data=ResponseInfo().format_response(
                    data={"code": "verification_service_unavailable"},
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    message="Email verification is temporarily unavailable.",
                ),
            )

        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data={
                    "email": user.email,
                    "next_step": "personal-details",
                    "verification_status": verification_status,
                    **oauth_session,
                },
                status_code=status.HTTP_200_OK,
                message=(
                    "This email is already verified. Continuing onboarding."
                    if verification_status == "already_verified"
                    else "Email verified successfully."
                ),
            ),
        )

    @action(detail=False, url_path="resend-email-verification", methods=["post"])
    def resend_email_verification(self, request, *args, **kwargs):
        email = str(request.data.get("email", "")).strip().lower()
        if not email:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={"code": "email_required"},
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="Email is required.",
                ),
            )

        user = User.objects.filter(email__iexact=email).first()
        generic_message = (
            "Your email address has not been verified yet. "
            "A new verification link has been sent to your email."
        )
        if not user:
            return Response(
                status=status.HTTP_200_OK,
                data=ResponseInfo().format_response(
                    data={},
                    status_code=status.HTTP_200_OK,
                    message=generic_message,
                ),
            )

        if user.is_verified:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={
                        "code": "email_already_verified",
                        "email": user.email,
                    },
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="This email is already verified. You can log in.",
                ),
            )

        try:
            send_verification_email(user)
        except VerificationEmailRecentlySent as exc:
            return Response(
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                data=ResponseInfo().format_response(
                    data={
                        "code": exc.code,
                        "retry_after": exc.retry_after,
                        "email": user.email,
                    },
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    message=str(exc),
                ),
            )
        except EmailVerificationError as exc:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={"code": exc.code, "email": exc.email},
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message=str(exc),
                ),
            )
        except Exception:
            logger.exception(
                "Could not resend verification email to user %s.",
                user.pk,
            )
            return Response(
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
                data=ResponseInfo().format_response(
                    data={"code": "verification_email_failed"},
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    message=(
                        "We could not send the verification email. Please try "
                        "again shortly."
                    ),
                ),
            )

        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data={"email": user.email},
                status_code=status.HTTP_200_OK,
                message=generic_message,
            ),
        )

    @action(detail=False, url_path="register-careseeker", methods=["post"])
    def register_careseeker(self, request, *args, **kwargs):
        email = str(request.data.get("email", "")).strip().lower()
        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            return Response(
                status=status.HTTP_409_CONFLICT,
                data=ResponseInfo().format_response(
                    data={
                        "code": "account_exists",
                        "email": existing_user.email,
                        "is_verified": existing_user.is_verified,
                        "can_resume_onboarding": (
                            Caregiver.objects.filter(user=existing_user).exists()
                            or Careseeker.objects.filter(
                                careseeker_user=existing_user
                            ).exists()
                        ),
                    },
                    status_code=status.HTTP_409_CONFLICT,
                    message=(
                        "An account already exists for this email. Log in to "
                        "resume onboarding or use another email."
                    ),
                ),
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        Careseeker.objects.create(
            careseeker_user=user,
            onboarding_resume={
                "status": "in_progress",
                "completed_steps": ["account"],
                "next_step": "verification",
            },
        )

        careseeker_role = Role.objects.filter(code="careseeker").first()
        if careseeker_role:
            UserRole.objects.get_or_create(user=user, role=careseeker_role)

        verification_email_sent = True
        try:
            send_verification_email(user, enforce_cooldown=False)
        except Exception:
            verification_email_sent = False
            logger.exception(
                "Could not send careseeker verification email to user %s.",
                user.pk,
            )

        return Response(
            status=status.HTTP_201_CREATED,
            data=ResponseInfo().format_response(
                data={
                    "email": user.email,
                    "verification_required": True,
                    "verification_email_sent": verification_email_sent,
                },
                status_code=status.HTTP_201_CREATED,
                message=(
                    "Account created. Check your email to verify your address "
                    "before continuing."
                    if verification_email_sent
                    else (
                        "Account created, but the verification email could not be "
                        "sent. Request another email to continue."
                    )
                ),
            ),
        )
    @action(detail=False, url_path="update-password", methods=["patch"])
    def update_password(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data=serializer.errors,
                    message="Please fix the highlighted fields.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                ),
            )

        old_password = serializer.validated_data.get("old_password")
        new_password = serializer.validated_data.get("new_password")

        user = request.user

        if not user.check_password(old_password):
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=ResponseInfo().format_response(
                    data={"old_password": ["Current password is incorrect."]},
                    message="Current password is incorrect.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                ),
            )

        with transaction.atomic():
            user.set_password(new_password)
            user.save(update_fields=["password"])
            RefreshToken.objects.filter(user=user).delete()
            AccessToken.objects.filter(user=user).delete()

        changed_at = timezone.now()
        user_agent = request.headers.get("X-Client-User-Agent") or request.META.get(
            "HTTP_USER_AGENT",
            "",
        )

        try:
            _send_password_changed_email(
                user,
                changed_at,
                _describe_user_agent(user_agent),
            )
        except Exception:
            logger.exception(
                "Could not send password change security email to user %s.",
                user.pk,
            )

        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data={},
                message="Password updated successfully. Please log in again.",
                status_code=status.HTTP_200_OK,
            ),
        )
