"""
Custom DRF permission classes for AEGIS role-based access control.

Usage:
    @api_view(['GET'])
    @permission_classes([IsAuthenticated, IsAdminUser])
    def admin_only_view(request): ...
"""
from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    """Allows access only to users with role='admin'."""
    message = "Admin access only."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, 'role')
            and request.user.role == 'admin'
        )


class IsParentUser(BasePermission):
    """Allows access only to users with role='parent'."""
    message = "Parent access only."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, 'role')
            and request.user.role == 'parent'
        )
