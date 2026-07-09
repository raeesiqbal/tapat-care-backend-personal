from django.db import transaction
from rest_framework import serializers

from apps.caregivers.models import (
    Caregiver,
    CaregiverCertification,
    CaregiverCondition,
    CaregiverEquipment,
    Certification,
)
from apps.caregivers.constants import PetType, TransportationComfort
from apps.caregivers.serializers.update_serializers import _update_resume_progress
from apps.utils.constants import ExperienceLevel
from apps.utils.models import Condition, Equipment


PET_TYPE_CHOICES = PetType.choices
PET_TYPE_VALUES = {value for value, _ in PET_TYPE_CHOICES}


def _choices_payload(choices):
    return [{"value": value, "label": label} for value, label in choices]


def qualifications_experience_options():
    condition_items = Condition.objects.filter(is_active=True).order_by("id")
    equipment_items = Equipment.objects.filter(is_active=True).order_by("id")

    return {
        "certifications": CertificationOptionSerializer(
            Certification.objects.filter(is_active=True).order_by("id"),
            many=True,
        ).data,
        "condition_experience_items": ExperienceItemOptionSerializer(
            condition_items,
            many=True,
        ).data,
        "equipment_experience_items": ExperienceItemOptionSerializer(
            equipment_items,
            many=True,
        ).data,
        "transportation_comfort": _choices_payload(
            TransportationComfort.choices
        ),
        "pet_types": _choices_payload(PET_TYPE_CHOICES),
        "skill_levels": _choices_payload(ExperienceLevel.choices),
    }


def serialize_qualifications_experience(caregiver: Caregiver) -> dict:
    certification_rows = (
        caregiver.caregiver_certifications.select_related("certification")
        .order_by("certification__id")
    )
    condition_rows = (
        caregiver.caregiver_conditions.select_related("condition")
        .order_by("condition__id")
    )
    equipment_rows = (
        caregiver.caregiver_equipments.select_related("equipment")
        .order_by("equipment__id")
    )

    return {
        "certifications": [
            {
                "id": row.certification_id,
                "name": row.certification.name,
                "slug": row.certification.slug,
                "verification_status": row.verification_status,
                "expiration_date": (
                    row.expiration_date.isoformat()
                    if row.expiration_date
                    else None
                ),
            }
            for row in certification_rows
        ],
        "transportation": {
            "has_drivers_license": caregiver.has_drivers_license,
            "has_car": caregiver.has_car,
            "has_auto_insurance_registration": (
                caregiver.has_auto_insurance_registration
            ),
            "transportation_comfort": caregiver.transportation_comfort,
        },
        "preferences": {
            "willing_with_pets": caregiver.willing_with_pets,
            "pet_types_comfortable": (
                caregiver.pet_types_comfortable
                if isinstance(caregiver.pet_types_comfortable, list)
                else []
            ),
            "willing_with_smokers": caregiver.willing_with_smokers,
        },
        "condition_experience": [
            _condition_row_payload(row)
            for row in condition_rows
        ],
        "equipment_experience": [
            _equipment_row_payload(row)
            for row in equipment_rows
        ],
    }


def _condition_row_payload(row: CaregiverCondition) -> dict:
    return {
        "item_id": row.condition_id,
        "name": row.condition.name,
        "slug": row.condition.slug,
        "item_type": "condition",
        "skill_level": row.skill_level,
    }


def _equipment_row_payload(row: CaregiverEquipment) -> dict:
    return {
        "item_id": row.equipment_id,
        "name": row.equipment.name,
        "slug": row.equipment.slug,
        "item_type": "equipment",
        "skill_level": row.skill_level,
    }


class CertificationOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certification
        fields = ["id", "name", "slug"]


class ExperienceItemOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    item_type = serializers.SerializerMethodField()

    def get_item_type(self, obj):
        if isinstance(obj, Condition):
            return "condition"
        return "equipment"


class TransportationSerializer(serializers.Serializer):
    has_drivers_license = serializers.BooleanField(required=True)
    has_car = serializers.BooleanField(required=True)
    has_auto_insurance_registration = serializers.BooleanField(required=True)
    transportation_comfort = serializers.ChoiceField(
        choices=TransportationComfort.choices,
        required=True,
    )

    def validate(self, attrs):
        comfort = attrs.get("transportation_comfort")
        if (
            comfort
            in {
                TransportationComfort.CAN_DRIVE_CLIENT,
                TransportationComfort.ERRANDS_ONLY,
            }
            and attrs.get("has_drivers_license") is not True
        ):
            raise serializers.ValidationError(
                {
                    "has_drivers_license": (
                        "A driver's license is required for this "
                        "transportation comfort level."
                    )
                }
            )
        if (
            attrs.get("has_auto_insurance_registration") is True
            and attrs.get("has_car") is not True
        ):
            raise serializers.ValidationError(
                {
                    "has_car": (
                        "Car ownership is required when auto insurance or "
                        "registration is provided."
                    )
                }
            )
        return attrs


class PreferencesSerializer(serializers.Serializer):
    willing_with_pets = serializers.BooleanField(required=True)
    pet_types_comfortable = serializers.ListField(
        child=serializers.ChoiceField(choices=PET_TYPE_CHOICES),
        required=False,
        allow_empty=True,
    )
    willing_with_smokers = serializers.BooleanField(required=True)

    def validate(self, attrs):
        willing_with_pets = attrs.get("willing_with_pets")
        pet_types = attrs.get("pet_types_comfortable", [])

        if willing_with_pets is False:
            attrs["pet_types_comfortable"] = []
            return attrs

        if not pet_types:
            raise serializers.ValidationError(
                {
                    "pet_types_comfortable": (
                        "Select at least one pet type when willing to work "
                        "with pets."
                    )
                }
            )

        invalid_pet_types = [
            pet_type for pet_type in pet_types if pet_type not in PET_TYPE_VALUES
        ]
        if invalid_pet_types:
            raise serializers.ValidationError(
                {"pet_types_comfortable": "One or more pet types are invalid."}
            )

        attrs["pet_types_comfortable"] = list(dict.fromkeys(pet_types))
        return attrs


class ExperienceSubmissionSerializer(serializers.Serializer):
    item_id = serializers.IntegerField(required=True)
    skill_level = serializers.ChoiceField(
        choices=ExperienceLevel.choices,
        required=True,
    )


class QualificationsExperienceSerializer(serializers.Serializer):
    certifications = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        allow_empty=True,
    )
    transportation = TransportationSerializer(required=True)
    preferences = PreferencesSerializer(required=True)
    condition_experience = ExperienceSubmissionSerializer(many=True, required=True)
    equipment_experience = ExperienceSubmissionSerializer(many=True, required=True)

    def validate_certifications(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Duplicate certifications are not allowed.")

        found_ids = set(
            Certification.objects.filter(id__in=value, is_active=True).values_list(
                "id",
                flat=True,
            )
        )
        missing_ids = [
            certification_id
            for certification_id in value
            if certification_id not in found_ids
        ]
        if missing_ids:
            raise serializers.ValidationError(
                "One or more certifications are inactive or unknown."
            )
        return value

    def validate(self, attrs):
        self._validate_experience_items(
            attrs.get("condition_experience", []),
            Condition,
            "condition_experience",
        )
        self._validate_experience_items(
            attrs.get("equipment_experience", []),
            Equipment,
            "equipment_experience",
        )
        return attrs

    def _validate_experience_items(self, submitted_items, model_class, field_name):
        item_ids = [item["item_id"] for item in submitted_items]
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError(
                {field_name: "Duplicate experience items are not allowed."}
            )

        active_items = model_class.objects.filter(
            id__in=item_ids,
            is_active=True,
        )
        if active_items.count() != len(item_ids):
            raise serializers.ValidationError(
                {field_name: "One or more experience items are inactive or unknown."}
            )

    @transaction.atomic
    def save(self, **kwargs):
        caregiver = self.context["caregiver"]
        data = self.validated_data
        transportation = data["transportation"]
        preferences = data["preferences"]

        for key, value in transportation.items():
            setattr(caregiver, key, value)
        for key, value in preferences.items():
            setattr(caregiver, key, value)

        _update_resume_progress(
            caregiver,
            completed_steps=["qualifications-experience"],
            next_step="screening-payment",
        )
        caregiver.save(
            update_fields=[
                "has_drivers_license",
                "has_car",
                "has_auto_insurance_registration",
                "transportation_comfort",
                "willing_with_pets",
                "pet_types_comfortable",
                "willing_with_smokers",
                "onboarding_resume",
                "updated_at",
            ]
        )

        caregiver.caregiver_certifications.all().delete()
        CaregiverCertification.objects.bulk_create(
            [
                CaregiverCertification(
                    caregiver=caregiver,
                    certification_id=certification_id,
                )
                for certification_id in data["certifications"]
            ]
        )

        caregiver.caregiver_conditions.all().delete()
        caregiver.caregiver_equipments.all().delete()
        CaregiverCondition.objects.bulk_create(
            [
                CaregiverCondition(
                    caregiver=caregiver,
                    condition_id=item["item_id"],
                    skill_level=item["skill_level"],
                )
                for item in data["condition_experience"]
            ]
        )
        CaregiverEquipment.objects.bulk_create(
            [
                CaregiverEquipment(
                    caregiver=caregiver,
                    equipment_id=item["item_id"],
                    skill_level=item["skill_level"],
                )
                for item in data["equipment_experience"]
            ]
        )

        return caregiver
