# imports
from apps.utils.views.base import BaseViewset, ResponseInfo
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
# models
from apps.caregivers.models import CaregiverSkill, Caregiver
# serializers
from apps.caregivers.serializers.create_serializers import CaregiverSkillCreateSerializer
from apps.caregivers.serializers.get_serializers import CaregiverSkillGetSerializer
from apps.caregivers.serializers.update_serializers import (
    CaregiverSkillUpdateSerializer,
    BulkDeleteSerializer,
)
# permissions
from apps.users.permissions import IsStaff, IsSuperUser
from apps.caregivers.permissions import IsCaregiver
from rest_framework.exceptions import ValidationError

class CaregiverSkillViewSet(BaseViewset):
    """
    API endpoints that manage caregiver skills  .
    """
    queryset = CaregiverSkill.objects.all().order_by("-created_at")
    user_role_queryset = {
        "caregiver": lambda view: view.queryset.filter(
            caregiver__user=view.request.user
        ),
        "staff": lambda view: view.queryset.all(),
        "superuser": lambda view: view.queryset.all(),
        "default": lambda view: view.queryset.none(),
    }
    action_serializers = {
        "default": CaregiverSkillGetSerializer,
        "create": CaregiverSkillCreateSerializer,
        "partial_update": CaregiverSkillUpdateSerializer,
        "bulk_delete": BulkDeleteSerializer,
    }
    action_permissions = {
        "default": [],
        "list": [],
        "retrieve": [],
        "create": [IsAuthenticated, IsStaff | IsSuperUser | IsCaregiver],
        "partial_update": [IsAuthenticated, IsStaff | IsSuperUser | IsCaregiver],
        "destroy": [IsAuthenticated, IsStaff | IsSuperUser | IsCaregiver],
        "bulk_delete": [IsAuthenticated, IsStaff | IsSuperUser | IsCaregiver],
    }

    filter_backends = [SearchFilter]
    search_param = "search"
    search_fields = ["name"]

    def _is_caregiver_only(self):
        role_codes = self._get_user_role_codes()
        if not role_codes:
            return False
        if "caregiver" not in role_codes:
            return False
        return "staff" not in role_codes and "superuser" not in role_codes

    def _get_request_caregiver(self):
        caregiver = Caregiver.objects.filter(user=self.request.user).first()
        if not caregiver:
            raise ValidationError("Caregiver profile not found for current user.")
        return caregiver

    def perform_create(self, serializer):
        if self._is_caregiver_only():
            caregiver = self._get_request_caregiver()
            serializer.save(caregiver=caregiver)
            return
        serializer.save()

    def perform_update(self, serializer):
        if self._is_caregiver_only():
            caregiver = self._get_request_caregiver()
            serializer.save(caregiver=caregiver)
            return
        serializer.save()

    @action(detail=False, url_path="bulk-delete", methods=["post"])
    def bulk_delete(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data.get("ids", [])
        queryset = CaregiverSkill.objects.filter(id__in=ids)
        if self._is_caregiver_only():
            caregiver = self._get_request_caregiver()
            queryset = queryset.filter(caregiver=caregiver)
        queryset.delete()
        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data=ids,
                status_code=status.HTTP_200_OK,
                message="Services deleted successfully",
            ),
        )
