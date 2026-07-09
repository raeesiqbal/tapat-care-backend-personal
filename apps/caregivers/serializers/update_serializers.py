# Imports
from apps.utils.serializers.base import BaseSerializer
from rest_framework import serializers
from apps.caregivers.models import (
    CaregiverSkill , Caregiver,
)
from apps.services.models import Service
from apps.users.models import UserProfile, UserAddress
from django.db import transaction
from apps.utils.services.zipcode_service import get_us_zip_details

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
    status = str(raw.get("status") or "in_progress").strip().lower()
    if not status:
        status = "in_progress"

    completed_steps: list[str] = []
    for step in raw.get("completed_steps", []):
        normalized = str(step).strip()
        if normalized in ONBOARDING_STEPS and normalized not in completed_steps:
            completed_steps.append(normalized)

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


def _update_resume_progress(
    caregiver: Caregiver,
    *,
    completed_steps: list[str] | None = None,
    next_step: str | None = None,
) -> None:
    state = _normalize_resume_state(caregiver)

    for step in completed_steps or []:
        normalized = str(step).strip()
        if normalized in ONBOARDING_STEPS and normalized not in state["completed_steps"]:
            state["completed_steps"].append(normalized)

    if next_step:
        normalized_next_step = str(next_step).strip()
        if normalized_next_step in ONBOARDING_STEPS:
            state["next_step"] = normalized_next_step

    if state["status"] in TERMINAL_ONBOARDING_STATUSES:
        state["next_step"] = "submitted"

    caregiver.onboarding_resume = state

# Serializers
class CaregiverSkillUpdateSerializer(BaseSerializer):
    class Meta:
        model = CaregiverSkill
        fields = [
            "level"
        ]
class CaregiverUpdateSerializer(serializers.ModelSerializer):
    services = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(),
        many=True,
        required=False,
    )
    hourly_rate_cents = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )
    years_experience = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )

    class Meta:
        model = Caregiver
        fields = [
            "headline",
            "bio",
            "hourly_rate_cents",
            "years_experience",
            "availability",
            "services",
        ]

    @transaction.atomic
    def update(self, instance, validated_data):
        services = validated_data.pop("services", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        _update_resume_progress(
            instance,
            completed_steps=["skills-availability"],
            next_step="qualifications-experience",
        )
        instance.save()
        if services is not None:
            instance.services.set(services)
        return instance
        
class CaregiverUserProfileSerializer(serializers.Serializer):
    fullName = serializers.CharField(required=False, allow_blank=True)
    pronouns = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender_identity = serializers.CharField(required=False, allow_blank=True)
    ethnicity = serializers.CharField(required=False, allow_blank=True)
    languages = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )


class CaregiverUserAddressSerializer(serializers.Serializer):
    line_1 = serializers.CharField(required=False, allow_blank=True)
    line_2 = serializers.CharField(required=False, allow_blank=True)
    zip = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True, read_only=True)
    state = serializers.CharField(required=False, allow_blank=True, read_only=True)
    def validate(self, attrs):
        zip_code = str(attrs.get("zip") or "").strip()
        if not zip_code:
            return attrs
        try:
            details = get_us_zip_details(zip_code)
        except ValueError as exc:
            raise serializers.ValidationError({"zip": str(exc)})
        except LookupError as exc:
            raise serializers.ValidationError({"zip": str(exc)})
        attrs["zip"] = details["zip_code"]
        attrs["city"] = details["city"]
        attrs["state"] = details["state"]
        return attrs


class CaregiverProfileUpdateSerializer(BaseSerializer):
    profile = CaregiverUserProfileSerializer(required=False, write_only=True)
    address = CaregiverUserAddressSerializer(required=False, write_only=True)

    class Meta:
        model = Caregiver
        fields = [
            "profile",
            "address",
        ]

    @transaction.atomic
    def update(self, instance, validated_data):
        user = instance.user
        profile_data = validated_data.get("profile")
        if profile_data:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            full_name = profile_data.get("fullName")
            if full_name:
                parts = full_name.strip().split()
                user.first_name = parts[0] if len(parts) > 0 else ""
                user.last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                user.save()
            for key in (
                "pronouns",
                "date_of_birth",
                "gender_identity",
                "ethnicity",
                "languages",
            ):
                if key in profile_data:
                    setattr(profile, key, profile_data[key])
            profile.save()
        address_data = validated_data.get("address")
        if address_data:
            address, _ = UserAddress.objects.get_or_create(user=user)
            for key in ("line_1", "line_2", "city", "state", "zip"):
                if key in address_data and address_data[key] is not None:
                    setattr(address, key, address_data[key])
            address.save()
        _update_resume_progress(
            instance,
            completed_steps=["personal-details"],
            next_step="skills-availability",
        )
        instance.save(update_fields=["onboarding_resume", "updated_at"])
        return instance
    
class BulkDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), required=True)
    class Meta:
        ref_name = "CaregiverBulkDelete"
