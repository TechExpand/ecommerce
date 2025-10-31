from rest_framework import permissions

class IsSuperAdmin(permissions.BasePermission):
    """
    Allows access only to users with super admin privileges.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser  # only true for super admins
        )