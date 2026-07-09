# Imports
from apps.utils.serializers.base import BaseSerializer
from rest_framework import serializers
from apps.services.models import (
    Service,
    ServiceCategory
)

# Serializers
class ServiceUpdateSerializer(BaseSerializer):
    class Meta:
        model = Service
        fields = [
            "name",
            "slug",
            "description",
            "service_category",  
        ]

class ServiceCategoriesUpdateGetSerializer(BaseSerializer):
    class Meta:
        model = ServiceCategory
        fields = [
            "name",
            "slug",
            "is_new",
            "is_active",
        ]

class BulkDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), required=True)
    class Meta:
        ref_name = "ServiceBulkDelete"
