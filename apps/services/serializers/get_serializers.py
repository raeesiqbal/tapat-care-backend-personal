# imports
from apps.utils.serializers.base import BaseSerializer
from rest_framework import serializers
from apps.services.models import (
    Service,
    ServiceCategory
    
)
from apps.users.models import User

# serializers
class ServiceGetSerializer(BaseSerializer):
    class Meta:
        model = Service
        fields = [
            "name",
            "slug",
            "description",
            "service_category",
        ]

class ServiceCategoriesGetSerializer(BaseSerializer):
    class Meta:
        model = ServiceCategory
        fields = [
            "name",
            "slug",
            "is_new",
            "is_active",
        ]
