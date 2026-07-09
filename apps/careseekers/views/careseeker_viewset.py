# imports
import json
from apps.utils.views.base import BaseViewset ,ResponseInfo
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter
from rest_framework.decorators import action
from apps.careseekers.models import Careseeker
from rest_framework.response import Response
from rest_framework import status
from apps.careseekers.serializers.create_serializers import CareSeekerCreateSerializer
from apps.careseekers.serializers.get_serializers import CareSeekerGetSerializer
from apps.careseekers.serializers.update_serializers import (
    CareSeekerCareNeedsOnboardingSerializer,
    CareSeekerProfileUpdateSerializer,
    CareSeekerUpdateSerializer,
)
from apps.users.models import UserAddress, UserProfile
from apps.users.permissions import IsEmailVerified, IsPhoneVerified, IsStaff, IsSuperUser
from apps.careseekers.permissions import IsCareSeeker

ONBOARDING_STEPS = (
    "account",
    "verification",
    "personal-details",
    "care-needs",
)
TERMINAL_ONBOARDING_STATUSES = {"completed"}


def _normalize_resume_state(careseeker: Careseeker) -> dict:
    raw = (
        careseeker.onboarding_resume
        if isinstance(careseeker.onboarding_resume, dict)
        else {}
    )
    status = str(raw.get("status") or "in_progress").strip().lower() or "in_progress"
    completed_steps: list[str] = []
    for step in raw.get("completed_steps", []):
        normalized = str(step).strip()
        if normalized in ONBOARDING_STEPS and normalized not in completed_steps:
            completed_steps.append(normalized)

    if not completed_steps:
        completed_steps = ["account"]
        if careseeker.careseeker_user.is_verified:
            completed_steps.append("verification")

    next_step = str(raw.get("next_step") or "").strip()
    if status in TERMINAL_ONBOARDING_STATUSES:
        next_step = "dashboard"
    elif next_step not in ONBOARDING_STEPS:
        for candidate in ONBOARDING_STEPS:
            if candidate not in completed_steps:
                next_step = candidate
                break
        else:
            next_step = "dashboard"

    return {
        "status": status,
        "completed_steps": completed_steps,
        "next_step": next_step,
    }

class CareSeekerViewSet(BaseViewset):
    """
    API endpoints that manage caregiver skills  .
    """
    queryset = Careseeker.objects.all().order_by("-created_at")
    user_role_queryset = {
        "careseeker": lambda view: view.queryset.filter(
        careseeker_user=view.request.user
        ),
        "staff": lambda view: view.queryset.all(),
        "superuser": lambda view: view.queryset.all(),
        "default": lambda view: view.queryset.none(),
    }

    action_serializers = {
        "default": CareSeekerGetSerializer,
        "create": CareSeekerCreateSerializer,
        "partial_update": CareSeekerUpdateSerializer,
        "update_profile" : CareSeekerProfileUpdateSerializer,
        "care_needs": CareSeekerCareNeedsOnboardingSerializer,
    }

    action_permissions = {
        "default": [],
        "list": [],
        "retrieve": [],
        "create": [IsAuthenticated, IsStaff | IsSuperUser],
        "partial_update": [IsAuthenticated, IsStaff | IsSuperUser | IsCareSeeker],
        "destroy": [IsAuthenticated, IsStaff | IsSuperUser],
        "update_profile": [IsAuthenticated, IsEmailVerified, IsPhoneVerified, IsCareSeeker],
        "care_needs": [IsAuthenticated, IsEmailVerified, IsPhoneVerified, IsCareSeeker],
        "onboarding_state": [IsAuthenticated, IsEmailVerified, IsCareSeeker],
    }

    filter_backends = [SearchFilter]
    search_param = "search"
    search_fields = ["name"]

    @action(detail=False, methods=["patch"], url_path="update-profile")
    def update_profile(self, request, *args, **kwargs):
        careseeker = (
            Careseeker.objects.select_related("careseeker_user")
            .filter(careseeker_user=request.user)
            .first()
        )
        if not careseeker:
            return Response(
                ResponseInfo().format_response(
                    data={},
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="Careseeker profile not found.",
                ),
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.get_serializer(
            careseeker,
            data=request.data,
            partial=True,
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

    @action(detail=False, methods=["get", "put", "patch"], url_path="care-needs")
    def care_needs(self, request, *args, **kwargs):
        careseeker = (
            Careseeker.objects.select_related("careseeker_user")
            .prefetch_related("family_contacts", "careseeker_conditions__condition")
            .filter(careseeker_user=request.user)
            .first()
        )
        if not careseeker:
            return Response(
                ResponseInfo().format_response(
                    data={},
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="Careseeker profile not found.",
                ),
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method.lower() == "get":
            serializer = self.get_serializer(careseeker)
            return Response(
                ResponseInfo().format_response(
                    data=serializer.data,
                    status_code=status.HTTP_200_OK,
                    message="Care needs fetched successfully.",
                ),
                status=status.HTTP_200_OK,
            )

        serializer = self.get_serializer(careseeker, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            ResponseInfo().format_response(
                data=serializer.data,
                status_code=status.HTTP_200_OK,
                message="Care needs saved successfully.",
            ),
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="onboarding-state")
    def onboarding_state(self, request, *args, **kwargs):
        careseeker = (
            Careseeker.objects.select_related("careseeker_user", "primary_address")
            .filter(careseeker_user=request.user)
            .first()
        )
        if not careseeker:
            return Response(
                ResponseInfo().format_response(
                    data={},
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="Careseeker profile not found.",
                ),
                status=status.HTTP_404_NOT_FOUND,
            )

        profile = UserProfile.objects.filter(user=request.user).first()
        address = careseeker.primary_address or UserAddress.objects.filter(
            user=request.user
        ).first()
        state = _normalize_resume_state(careseeker)
        careseeker.onboarding_resume = state
        careseeker.save(update_fields=["onboarding_resume", "updated_at"])

        full_name = " ".join(
            filter(
                None,
                [
                    str(request.user.first_name or "").strip(),
                    str(request.user.last_name or "").strip(),
                ],
            )
        ).strip()

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
                    else (
                        careseeker.birth_date.isoformat()
                        if careseeker.birth_date
                        else ""
                    )
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
            "care-needs": CareSeekerCareNeedsOnboardingSerializer(careseeker).data,
        }

        return Response(
            ResponseInfo().format_response(
                data={
                    "onboarding": state,
                    "account_status": careseeker.account_status,
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
