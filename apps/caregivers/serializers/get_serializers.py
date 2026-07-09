# imports
from apps.utils.serializers.base import BaseSerializer
from rest_framework import serializers
# models
from apps.caregivers.models import (
    CaregiverSkill , Caregiver,
)
from apps.users.models import UserAddress
# serializers
class CaregiverSkillGetSerializer(BaseSerializer):
    class Meta:
        model = CaregiverSkill
        fields = [
            "skill",
            "caregiver",
            "level",
        ]   

class CaregiverGetSerializer(BaseSerializer):
    name = serializers.SerializerMethodField()
    picture = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    hourly_rate_cents = serializers.IntegerField(read_only=True)
    years_experience = serializers.IntegerField(read_only=True)

    class Meta:
        model = Caregiver
        fields = [
            "user",
            "name",
            "picture",
            "location",
            "headline",
            "bio",
            "hourly_rate_cents",
            "years_experience",
            "account_status",
            "screening_status",
            "services",
        ]

    def get_name(self, obj):
        full_name = " ".join(
            filter(
                None,
                [
                    str(obj.user.first_name or "").strip(),
                    str(obj.user.last_name or "").strip(),
                ],
            )
        ).strip()
        return full_name or str(obj.user.email or "").strip() or "Caregiver"

    def get_picture(self, obj):
        return obj.user.picture or None

    def get_location(self, obj):
        prefetched_addresses = getattr(obj.user, "dashboard_addresses", None)
        address = (
            prefetched_addresses[0]
            if prefetched_addresses
            else UserAddress.objects.filter(user=obj.user).order_by("-created_at").first()
        )

        if not address:
            return "Location not available"

        city_state = ", ".join(
            value
            for value in [
                str(address.city or "").strip(),
                str(address.state or "").strip(),
            ]
            if value
        )
        zip_code = str(address.zip or "").strip()

        if city_state and zip_code:
            return f"{city_state} - {zip_code}"

        return city_state or zip_code or "Location not available"

    def get_services(self, obj):
        return [service.name for service in obj.services.all()]
