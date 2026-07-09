# Imports
from apps.utils.serializers.base import BaseSerializer
from rest_framework import serializers
# Models
from apps.careseekers.models import (
    Careseeker
)

class CareSeekerGetSerializer(BaseSerializer):
    class Meta:
        model = Careseeker
        fields = [
            "careseeker_user",
            "birth_date",
            "primary_address",
            "onboarding_resume",
            "account_status",
        ]
