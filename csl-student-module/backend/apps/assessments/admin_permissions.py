from rest_framework.permissions import BasePermission
from apps.users.models import User


class IsCSLAdminUser(BasePermission):
    """
    Strict authorization check:
    Grants access only to authenticated users with is_staff=True, is_superuser=True,
    or User.role == 'ADMIN'.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        
        # Check active status
        if getattr(user, "status", None) != User.AccountStatus.ACTIVE:
            return False

        return bool(
            user.is_staff
            or user.is_superuser
            or getattr(user, "role", None) == User.Role.ADMIN
        )
