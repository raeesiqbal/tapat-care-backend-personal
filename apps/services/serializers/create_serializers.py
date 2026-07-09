# Imports
from apps.utils.serializers.base import BaseSerializer
from rest_framework import serializers
from apps.services.models import (
    Service,
    ServiceCategory
)

class ServiceCreateSerializer(BaseSerializer):
    class Meta:
        model = Service
        fields = [
            "name",
            "description",
            "service_category", 
        ]
        
class ServiceCategoriesCreateSerializer(BaseSerializer):
    class Meta:
        model = ServiceCategory
        fields = [
            "name",
            "is_new",
            "is_active",
        ]

