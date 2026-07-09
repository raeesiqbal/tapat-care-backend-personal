# imports
from apps.utils.views.base import BaseViewset, ResponseInfo
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from apps.services.models import ServiceCategory

# serializers
from apps.services.serializers.create_serializers import ServiceCategoriesCreateSerializer
from apps.services.serializers.get_serializers import ServiceCategoriesGetSerializer
from apps.services.serializers.update_serializers import (
    ServiceCategoriesUpdateGetSerializer,
    BulkDeleteSerializer,
)

# permissions
from apps.users.permissions import IsStaff, IsSuperUser


class ServiceCategoriesViewSet(BaseViewset):
    """
    API endpoints that manage service categories.
    """

    queryset = ServiceCategory.objects.all().order_by("-created_at") 

    action_serializers = {
        "default": ServiceCategoriesGetSerializer,
        "create": ServiceCategoriesCreateSerializer,
        "partial_update": ServiceCategoriesUpdateGetSerializer,
        "bulk_delete": BulkDeleteSerializer,
    }

    action_permissions = {
        "default": [],
        "list": [],
        "retrieve": [],
        "create": [IsAuthenticated, IsStaff | IsSuperUser],
        "partial_update": [IsAuthenticated, IsStaff | IsSuperUser],
        "destroy": [IsAuthenticated, IsStaff | IsSuperUser],
        "bulk_delete": [IsAuthenticated, IsStaff | IsSuperUser],
    }

    user_role_queryset = {
        "staff": lambda view: view.queryset.all(),
        "superuser": lambda view: view.queryset.all(),
        "default": lambda view: view.queryset.all(),
    }

    filter_backends = [SearchFilter]
    search_param = "search"
    search_fields = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get("name")
        if name:
            queryset = queryset.filter(name__iexact=name)
        return queryset

    @action(detail=False, url_path="bulk-delete", methods=["post"])
    def bulk_delete(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data.get("ids", [])
        ServiceCategory.objects.filter(id__in=ids).delete()
        return Response(
            status=status.HTTP_200_OK,
            data=ResponseInfo().format_response(
                data=ids,
                status_code=status.HTTP_200_OK,
                message="Service categories deleted successfully",
            ),
        )
