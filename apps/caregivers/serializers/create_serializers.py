# Imports
from apps.utils.serializers.base import BaseSerializer
from rest_framework import serializers
# Models
from apps.caregivers.models import (
    CaregiverSkill ,Caregiver,
)

class CaregiverSkillCreateSerializer(BaseSerializer):
    class Meta:
        model = CaregiverSkill
        fields = [
            "skill",
            "caregiver",
            "level",
        ]

class CaregiverCreateSerializer(BaseSerializer):
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
            "user",
            "headline",
            "bio",
            "hourly_rate_cents",
            "years_experience",
        ]
