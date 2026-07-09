from rest_framework import permissions


class IsStaff(permissions.BasePermission):
    """
    Permission check for Staff role verification.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_staff

class IsSuperUser(permissions.BasePermission):
    """
    Permission check for IsSuper User.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_superuser


class IsEmailVerified(permissions.BasePermission):
    message = "Verify your email before continuing onboarding."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_verified
        )


class IsPhoneVerified(permissions.BasePermission):
    message = "Verify your phone number before continuing onboarding."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.phone_verified_at
        )
