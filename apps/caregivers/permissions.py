from rest_framework import permissions
from apps.users.models import UserRole, Role

class IsCaregiver(permissions.BasePermission):
    """
    Permission check for Caregiver role verification.
    """

    def has_permission(self, request, view):
        if request.user:
            caregiver_role = Role.objects.filter(code="caregiver").first()
            return UserRole.objects.filter(user=request.user, role=caregiver_role).exists()
        return False