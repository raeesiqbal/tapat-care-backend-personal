# imports
import json
from django.db.models import Prefetch
from apps.utils.views.base import BaseViewset ,ResponseInfo
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter
from rest_framework.decorators import action
from apps.caregivers.models import Caregiver
from rest_framework.response import Response
from rest_framework import status
from apps.caregivers.serializers.create_serializers import CaregiverCreateSerializer
from apps.caregivers.serializers.get_serializers import (
    CaregiverDetailGetSerializer,
    CaregiverGetSerializer,
)
from apps.caregivers.serializers.update_serializers import (
    CaregiverProfileUpdateSerializer,CaregiverUpdateSerializer
)
from apps.caregivers.serializers.qualifications_experience import (
    serialize_qualifications_experience,
)
from apps.users.models import UserAddress, UserProfile
from apps.users.permissions import IsEmailVerified, IsPhoneVerified, IsStaff, IsSuperUser
from apps.caregivers.permissions import IsCaregiver

ONBOARDING_STEPS = (
    "account",
    "verification",
    "personal-details",
    "skills-availability",
    "qualifications-experience",
    "screening-payment",
    "submitted",
)
TERMINAL_ONBOARDING_STATUSES = {"completed", "in_review", "under_review"}


def _normalize_resume_state(caregiver: Caregiver) -> dict:
    raw = caregiver.onboarding_resume if isinstance(caregiver.onboarding_resume, dict) else {}
    status = str(raw.get("status") or "in_progress").strip().lower() or "in_progress"
    completed_steps: list[str] = []
    for step in raw.get("completed_steps", []):
        normalized = str(step).strip()
        if normalized in ONBOARDING_STEPS and normalized not in completed_steps:
            completed_steps.append(normalized)

    if not completed_steps:
        completed_steps = ["account"]
        if caregiver.user.is_verified:
            completed_steps.append("verification")

    next_step = str(raw.get("next_step") or "").strip()
    if status in TERMINAL_ONBOARDING_STATUSES:
        next_step = "submitted"
    elif next_step not in ONBOARDING_STEPS:
        for candidate in ONBOARDING_STEPS:
            if candidate not in completed_steps:
                next_step = candidate
                break
        else:
            next_step = "submitted"

    return {
        "status": status,
        "completed_steps": completed_steps,
        "next_step": next_step,
    }


def _format_hourly_rate_value(hourly_rate_cents: int | None) -> str:
    if hourly_rate_cents is None:
        return ""

    dollars = hourly_rate_cents / 100
    value = f"{dollars:.2f}"
    return value.rstrip("0").rstrip(".")


def _format_years_experience_value(years_experience: int | None) -> str:
    if years_experience is None:
        return ""

    return str(years_experience)


class CaregiverViewSet(BaseViewset):
    """
    API endpoints that manage caregiver skills  .
    """
    queryset = (
        Caregiver.objects.select_related("user")
        .prefetch_related(
            "services",
            Prefetch(
                "user__useraddress_set",
                queryset=UserAddress.objects.order_by("-created_at"),
                to_attr="dashboard_addresses",
            ),
        )
        .order_by("-created_at")
    )
    user_role_queryset = {
        "caregiver": lambda view: view.queryset.filter(
            user=view.request.user
        ),
        "careseeker": lambda view: view.queryset.all(),
        "staff": lambda view: view.queryset.all(),
        "superuser": lambda view: view.queryset.all(),
        "default": lambda view: view.queryset.none(),
    }

    action_serializers = {
        "default": CaregiverGetSerializer,
        "create": CaregiverCreateSerializer,
        "retrieve": CaregiverDetailGetSerializer,
        "partial_update": CaregiverUpdateSerializer,
        "update_profile" : CaregiverUpdateSerializer,
    }

    action_permissions = {
        "default": [],
        "list": [IsAuthenticated],
        "retrieve": [IsAuthenticated],
        "create": [IsAuthenticated, IsStaff | IsSuperUser],
        "partial_update": [IsAuthenticated, IsStaff | IsSuperUser | IsCaregiver],
        "destroy": [IsAuthenticated, IsStaff | IsSuperUser],
        "update_profile": [IsAuthenticated, IsEmailVerified, IsPhoneVerified, IsCaregiver],
        "onboarding_state": [IsAuthenticated, IsEmailVerified, IsCaregiver],
    }

    filter_backends = [SearchFilter]
    search_param = "search"
    search_fields = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.action == "retrieve":
            return queryset.select_related("user__profile").prefetch_related(
                "services__service_category",
                "caregiver_certifications__certification",
                "caregiver_conditions__condition",
                "caregiver_equipments__equipment",
            )

        return queryset

    @action(detail=False, methods=["patch"], url_path="update-profile")
    def update_profile(self, request, *args, **kwargs):
        caregiver = (
            Caregiver.objects.select_related("user")
            .filter(user=request.user)
            .first()
        )
        if not caregiver:
            return Response(
                ResponseInfo().format_response(
                    data={},
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="Caregiver profile not found.",
                ),
                status=status.HTTP_404_NOT_FOUND,
            )

        uses_profile_payload = any(
            key in request.data for key in ("profile", "address")
        )
        serializer_class = (
            CaregiverProfileUpdateSerializer
            if uses_profile_payload
            else CaregiverUpdateSerializer
        )

        serializer = serializer_class(
            caregiver,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            ResponseInfo().format_response(
                data=serializer.data,
                status_code=status.HTTP_200_OK,
                message="Profile updated successfully",
            ),
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="onboarding-state")
    def onboarding_state(self, request, *args, **kwargs):
        caregiver = (
            Caregiver.objects.select_related("user")
            .prefetch_related("services")
            .filter(user=request.user)
            .first()
        )
        if not caregiver:
            return Response(
                ResponseInfo().format_response(
                    data={},
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="Caregiver profile not found.",
                ),
                status=status.HTTP_404_NOT_FOUND,
            )

        profile = UserProfile.objects.filter(user=request.user).first()
        address = UserAddress.objects.filter(user=request.user).first()
        state = _normalize_resume_state(caregiver)
        caregiver.onboarding_resume = state
        caregiver.save(update_fields=["onboarding_resume", "updated_at"])

        full_name = " ".join(
            filter(
                None,
                [
                    str(request.user.first_name or "").strip(),
                    str(request.user.last_name or "").strip(),
                ],
            )
        ).strip()
        services = list(caregiver.services.values_list("id", flat=True))
        availability = caregiver.availability if isinstance(caregiver.availability, list) else []

        values_by_step = {
            "account": {
                "email": str(request.user.email or ""),
                "phone": str(request.user.phone or ""),
            },
            "verification": {
                "phone": str(request.user.phone or ""),
                "phoneVerified": "true" if request.user.phone_verified_at else "false",
            },
            "personal-details": {
                "fullName": full_name,
                "pronouns": str(getattr(profile, "pronouns", "") or ""),
                "birthDate": (
                    getattr(profile, "date_of_birth", None).isoformat()
                    if getattr(profile, "date_of_birth", None)
                    else ""
                ),
                "genderIdentity": str(getattr(profile, "gender_identity", "") or ""),
                "ethnicity": str(getattr(profile, "ethnicity", "") or ""),
                "languages": json.dumps(
                    getattr(profile, "languages", [])
                    if isinstance(getattr(profile, "languages", []), list)
                    else []
                ),
                "line1": str(getattr(address, "line_1", "") or ""),
                "line2": str(getattr(address, "line_2", "") or ""),
                "zip": str(getattr(address, "zip", "") or ""),
            },
            "skills-availability": {
                "services": json.dumps(services),
                "hourlyRate": _format_hourly_rate_value(
                    caregiver.hourly_rate_cents
                ),
                "yearsExperience": _format_years_experience_value(
                    caregiver.years_experience
                ),
                "availability": json.dumps(availability),
                "bio": str(caregiver.bio or ""),
            },
            "qualifications-experience": serialize_qualifications_experience(
                caregiver
            ),
        }

        return Response(
            ResponseInfo().format_response(
                data={
                    "onboarding": state,
                    "account_status": caregiver.account_status,
                    "screening_status": caregiver.screening_status,
                    "phone": str(request.user.phone or ""),
                    "phone_verified": bool(request.user.phone_verified_at),
                    "saved_steps": state["completed_steps"],
                    "values_by_step": values_by_step,
                },
                status_code=status.HTTP_200_OK,
                message="Onboarding state fetched successfully.",
            ),
            status=status.HTTP_200_OK,
        )
