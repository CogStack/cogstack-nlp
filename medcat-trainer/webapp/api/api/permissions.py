from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from .models import ProjectAnnotateEntities, ProjectGroup


class IsReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow read-only operations.
    """

    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        return request.method in permissions.SAFE_METHODS


def is_project_admin(user, project):
    """
    Check if a user is an admin of a project.
    A user is a project admin if:
    1. They are a member of the project, OR
    2. They are an administrator of the project's group (if the project has a group)
    3. They are a superuser/staff
    """
    if user.is_superuser or user.is_staff:
        return True

    # Check if user is a member of the project
    if project.members.filter(id=user.id).exists():
        return True

    # Check if user is an administrator of the project's group
    if project.group and project.group.administrators.filter(id=user.id).exists():
        return True

    return False
