from rest_framework import permissions

class IsReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow read-only operations.
    """

    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        return request.method in permissions.SAFE_METHODS
