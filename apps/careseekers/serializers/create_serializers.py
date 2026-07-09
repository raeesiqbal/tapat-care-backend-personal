# Imports
from apps.utils.serializers.base import BaseSerializer
from rest_framework import serializers
# Models
from apps.careseekers.models import (
    Careseeker
)

class CareSeekerCreateSerializer(BaseSerializer):
    class Meta:
        model = Careseeker
        fields = [
            "birth_date",
            "primary_address",
        ]
