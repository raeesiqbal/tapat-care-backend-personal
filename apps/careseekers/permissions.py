from rest_framework import permissions
from apps.users.models import UserRole, Role

class IsCareSeeker(permissions.BasePermission):
    """
    Permission check for Careseeker role verification.
    """

    def has_permission(self, request, view):
        if request.user:
            careseeker_role = Role.objects.filter(code="careseeker").first()
            return UserRole.objects.filter(user=request.user, role=careseeker_role).exists()
        return False