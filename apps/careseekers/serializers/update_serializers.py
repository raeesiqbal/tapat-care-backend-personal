# Imports
from apps.utils.serializers.base import BaseSerializer
from rest_framework import serializers
from django.db import transaction
from apps.careseekers.models import (
    Careseeker,
    CareseekerCondition,
    CareseekerEquipment,
    FamilyContact,
)
from apps.careseekers.constants import (
    ContactPriority,
    Continence,
    Mobility,
    PreferredCaregiverGender,
    StandingAbility,
    TransportationMode,
)
from apps.utils.constants import ConditionStage, ExperienceLevel
from apps.utils.models import Condition, Equipment
from apps.users.models import UserAddress, UserProfile
from apps.utils.services.zipcode_service import get_us_zip_details

ONBOARDING_STEPS = (
    "account",
    "verification",
    "personal-details",
    "care-needs",
)
TERMINAL_ONBOARDING_STATUSES = {"completed"}
CARE_NEEDS_FIELDS = (
    "lives_alone",
    "mobility",
    "can_stand",
    "lifting_required",
    "lifting_level",
    "continence",
    "medication_reminder_needed",
    "preferred_caregiver_gender",
    "driver_needed",
    "transportation_mode",
    "pets_at_home",
)


def _choices_payload(choices):
    return [{"value": value, "label": label} for value, label in choices]


def _normalize_resume_state(careseeker: Careseeker) -> dict:
    raw = (
        careseeker.onboarding_resume
        if isinstance(careseeker.onboarding_resume, dict)
        else {}
    )
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


def _update_resume_progress(
    careseeker: Careseeker,
    *,
    completed_steps: list[str] | None = None,
    next_step: str | None = None,
    status: str | None = None,
) -> None:
    state = _normalize_resume_state(careseeker)
    for step in completed_steps or []:
        normalized = str(step).strip()
        if normalized in ONBOARDING_STEPS and normalized not in state["completed_steps"]:
            state["completed_steps"].append(normalized)

    if status:
        state["status"] = str(status).strip().lower()

    if next_step:
        normalized_next_step = str(next_step).strip()
        state["next_step"] = (
            normalized_next_step
            if normalized_next_step in ONBOARDING_STEPS or normalized_next_step == "dashboard"
            else state["next_step"]
        )

    if state["status"] in TERMINAL_ONBOARDING_STATUSES:
        state["next_step"] = "dashboard"

    careseeker.onboarding_resume = state


class CareSeekerUpdateSerializer(BaseSerializer):
    class Meta:
        model = Careseeker
        fields = [
            "careseeker_user",
            "birth_date",
            "primary_address",
            "onboarding_resume",
        ]


class CareSeekerUserProfileSerializer(serializers.Serializer):
    fullName = serializers.CharField(required=False, allow_blank=True)
    pronouns = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender_identity = serializers.CharField(required=False, allow_blank=True)
    ethnicity = serializers.CharField(required=False, allow_blank=True)
    languages = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )


class CareSeekerUserAddressSerializer(serializers.Serializer):
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


class CareSeekerProfileUpdateSerializer(BaseSerializer):
    profile = CareSeekerUserProfileSerializer(required=False, write_only=True)
    address = CareSeekerUserAddressSerializer(required=False, write_only=True)

    class Meta:
        model = Careseeker
        fields = [
            "profile",
            "address",
        ]

    @transaction.atomic
    def update(self, instance, validated_data):
        user = instance.careseeker_user
        profile_data = validated_data.get("profile")
        if profile_data:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            full_name = profile_data.get("fullName")
            if full_name:
                parts = full_name.strip().split()
                user.first_name = parts[0] if len(parts) > 0 else ""
                user.last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                user.save(update_fields=["first_name", "last_name"])

            if "date_of_birth" in profile_data:
                instance.birth_date = profile_data["date_of_birth"]

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
            instance.primary_address = address

        _update_resume_progress(
            instance,
            completed_steps=["personal-details"],
            next_step="care-needs",
        )
        instance.save(
            update_fields=[
                "birth_date",
                "primary_address",
                "onboarding_resume",
                "updated_at",
            ]
        )
        return instance


class FamilyContactSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = FamilyContact
        fields = [
            "id",
            "name",
            "phone",
            "email",
            "relationship",
            "contact_priority",
        ]

    def validate_phone(self, value):
        phone = str(value or "").strip()
        if not phone:
            raise serializers.ValidationError("Phone is required.")
        return phone


class CareseekerConditionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    condition_id = serializers.PrimaryKeyRelatedField(
        source="condition",
        queryset=Condition.objects.filter(is_active=True),
    )
    condition_name = serializers.CharField(source="condition.name", read_only=True)
    condition_slug = serializers.CharField(source="condition.slug", read_only=True)

    class Meta:
        model = CareseekerCondition
        fields = [
            "id",
            "condition_id",
            "condition_name",
            "condition_slug",
            "condition_stage",
        ]


class ConditionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Condition
        fields = [
            "id",
            "name",
            "slug",
        ]


class CareseekerEquipmentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    equipment_id = serializers.PrimaryKeyRelatedField(
        source="equipment",
        queryset=Equipment.objects.filter(is_active=True),
    )
    equipment_name = serializers.CharField(source="equipment.name", read_only=True)
    equipment_slug = serializers.CharField(source="equipment.slug", read_only=True)

    class Meta:
        model = CareseekerEquipment
        fields = [
            "id",
            "equipment_id",
            "equipment_name",
            "equipment_slug",
            "skill_level",
        ]


class EquipmentOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipment
        fields = [
            "id",
            "name",
            "slug",
        ]


def care_needs_options():
    conditions = Condition.objects.filter(is_active=True).order_by("name")
    equipment = Equipment.objects.filter(is_active=True).order_by("name")

    return {
        "mobility": _choices_payload(Mobility.choices),
        "standing_ability": _choices_payload(StandingAbility.choices),
        "continence": _choices_payload(Continence.choices),
        "condition_stages": _choices_payload(ConditionStage.choices),
        "preferred_caregiver_gender": _choices_payload(
            PreferredCaregiverGender.choices
        ),
        "transportation_modes": _choices_payload(TransportationMode.choices),
        "contact_priorities": _choices_payload(ContactPriority.choices),
        "conditions": ConditionOptionSerializer(conditions, many=True).data,
        "equipment": EquipmentOptionSerializer(equipment, many=True).data,
        "skill_levels": _choices_payload(ExperienceLevel.choices),
    }


class CareNeedsFieldsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Careseeker
        fields = CARE_NEEDS_FIELDS
        extra_kwargs = {
            "lives_alone": {"required": True, "allow_null": False},
            "mobility": {"required": True, "allow_null": False, "allow_blank": False},
            "can_stand": {"required": True, "allow_null": False, "allow_blank": False},
            "lifting_required": {"required": True, "allow_null": False},
            "continence": {"required": True, "allow_null": False, "allow_blank": False},
            "medication_reminder_needed": {"required": True, "allow_null": False},
            "preferred_caregiver_gender": {
                "required": True,
                "allow_null": False,
                "allow_blank": False,
            },
            "driver_needed": {"required": True, "allow_null": False},
            "pets_at_home": {"required": True, "allow_null": False},
        }

    def validate(self, attrs):
        lifting_required = attrs.get("lifting_required")
        if lifting_required is False:
            attrs["lifting_level"] = None

        driver_needed = attrs.get("driver_needed")
        transportation_mode = attrs.get("transportation_mode")
        if driver_needed is True and not transportation_mode:
            raise serializers.ValidationError(
                {"transportation_mode": "Transportation mode is required when a driver is needed."}
            )
        if driver_needed is False:
            attrs["transportation_mode"] = None

        return attrs


class CareSeekerCareNeedsOnboardingSerializer(serializers.Serializer):
    family_contacts = FamilyContactSerializer(many=True)
    care_needs = CareNeedsFieldsSerializer()
    conditions = CareseekerConditionSerializer(many=True, required=False)
    equipment = CareseekerEquipmentSerializer(many=True, required=False)
    onboarding = serializers.SerializerMethodField(read_only=True)

    def validate_family_contacts(self, value):
        if not value:
            raise serializers.ValidationError("At least one family contact is required.")

        primary_count = sum(
            1
            for contact in value
            if contact.get("contact_priority") == FamilyContact.ContactPriority.PRIMARY
        )
        if primary_count == 0:
            raise serializers.ValidationError("At least one primary family contact is required.")
        if primary_count > 1:
            raise serializers.ValidationError("Only one primary family contact is allowed.")

        return value

    def validate_conditions(self, value):
        condition_ids = [item["condition"].id for item in value]
        if len(condition_ids) != len(set(condition_ids)):
            raise serializers.ValidationError("Duplicate conditions are not allowed.")
        return value

    def validate_equipment(self, value):
        equipment_ids = [item["equipment"].id for item in value]
        if len(equipment_ids) != len(set(equipment_ids)):
            raise serializers.ValidationError("Duplicate equipment is not allowed.")
        return value

    def validate(self, attrs):
        careseeker = self.instance
        if not careseeker:
            return attrs

        family_contact_ids = [
            contact["id"] for contact in attrs.get("family_contacts", []) if "id" in contact
        ]
        if family_contact_ids:
            valid_count = FamilyContact.objects.filter(
                careseeker=careseeker,
                id__in=family_contact_ids,
            ).count()
            if valid_count != len(set(family_contact_ids)):
                raise serializers.ValidationError(
                    {"family_contacts": "One or more family contacts do not belong to this careseeker."}
                )

        condition_row_ids = [
            condition["id"] for condition in attrs.get("conditions", []) if "id" in condition
        ]
        if condition_row_ids:
            valid_count = CareseekerCondition.objects.filter(
                careseeker=careseeker,
                id__in=condition_row_ids,
            ).count()
            if valid_count != len(set(condition_row_ids)):
                raise serializers.ValidationError(
                    {"conditions": "One or more condition rows do not belong to this careseeker."}
                )

        equipment_row_ids = [
            equipment["id"] for equipment in attrs.get("equipment", []) if "id" in equipment
        ]
        if equipment_row_ids:
            valid_count = CareseekerEquipment.objects.filter(
                careseeker=careseeker,
                id__in=equipment_row_ids,
            ).count()
            if valid_count != len(set(equipment_row_ids)):
                raise serializers.ValidationError(
                    {"equipment": "One or more equipment rows do not belong to this careseeker."}
                )

        return attrs

    def get_onboarding(self, obj):
        return _normalize_resume_state(obj)

    def to_representation(self, instance):
        options = care_needs_options()

        return {
            "family_contacts": FamilyContactSerializer(
                instance.family_contacts.order_by("id"),
                many=True,
            ).data,
            "care_needs": CareNeedsFieldsSerializer(instance).data,
            "conditions": CareseekerConditionSerializer(
                instance.careseeker_conditions.select_related("condition").order_by("id"),
                many=True,
            ).data,
            "equipment": CareseekerEquipmentSerializer(
                instance.careseeker_equipments.select_related("equipment").order_by("id"),
                many=True,
            ).data,
            "options": options,
            "condition_options": options["conditions"],
            "equipment_options": options["equipment"],
            "skill_levels": options["skill_levels"],
            "onboarding": _normalize_resume_state(instance),
        }

    @transaction.atomic
    def update(self, instance, validated_data):
        care_needs = validated_data["care_needs"]
        family_contacts = validated_data["family_contacts"]
        conditions = validated_data.get("conditions", [])
        equipment = validated_data.get("equipment", [])

        for field in CARE_NEEDS_FIELDS:
            if field in care_needs:
                setattr(instance, field, care_needs[field])

        _update_resume_progress(
            instance,
            completed_steps=["care-needs"],
            next_step="dashboard",
            status="completed",
        )
        instance.account_status = Careseeker.AccountStatus.APPROVED
        instance.save(
            update_fields=[
                *CARE_NEEDS_FIELDS,
                "onboarding_resume",
                "account_status",
                "updated_at",
            ]
        )

        incoming_contact_ids = [
            contact["id"] for contact in family_contacts if "id" in contact
        ]
        FamilyContact.objects.filter(careseeker=instance).exclude(
            id__in=incoming_contact_ids
        ).delete()
        retained_contact_ids = []
        for contact_data in family_contacts:
            contact_id = contact_data.pop("id", None)
            contact, _ = FamilyContact.objects.update_or_create(
                id=contact_id,
                careseeker=instance,
                defaults=contact_data,
            )
            retained_contact_ids.append(contact.id)
        FamilyContact.objects.filter(careseeker=instance).exclude(
            id__in=retained_contact_ids
        ).delete()

        incoming_condition_ids = [
            condition["id"] for condition in conditions if "id" in condition
        ]
        CareseekerCondition.objects.filter(careseeker=instance).exclude(
            id__in=incoming_condition_ids
        ).delete()
        retained_condition_ids = []
        for condition_data in conditions:
            row_id = condition_data.pop("id", None)
            condition, _ = CareseekerCondition.objects.update_or_create(
                id=row_id,
                careseeker=instance,
                defaults=condition_data,
            )
            retained_condition_ids.append(condition.id)
        CareseekerCondition.objects.filter(careseeker=instance).exclude(
            id__in=retained_condition_ids
        ).delete()

        incoming_equipment_ids = [
            item["id"] for item in equipment if "id" in item
        ]
        CareseekerEquipment.objects.filter(careseeker=instance).exclude(
            id__in=incoming_equipment_ids
        ).delete()
        retained_equipment_ids = []
        for equipment_data in equipment:
            row_id = equipment_data.pop("id", None)
            equipment_row, _ = CareseekerEquipment.objects.update_or_create(
                id=row_id,
                careseeker=instance,
                defaults=equipment_data,
            )
            retained_equipment_ids.append(equipment_row.id)
        CareseekerEquipment.objects.filter(careseeker=instance).exclude(
            id__in=retained_equipment_ids
        ).delete()

        return instance
