from django.contrib.auth.forms import User
from rest_framework import permissions
from .models import ProjectAnnotateEntities


class IsReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow read-only operations.
    """

    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        return request.method in permissions.SAFE_METHODS


def is_project_admin(user: [User], project: [ProjectAnnotateEntities]):
    """
    Check if a user is an admin of a project.
    A user is a project admin if:
    1. They are a superuser/staff, OR
    2. They are a member of the project, OR
    3. They are an administrator of the project's group (if the project has a group), OR
    4. A registered ``is_project_admin`` permission hook grants access.

    Hooks are grant-only (see :mod:`api.extensions`): they may extend the set
    of users considered admins (e.g. via OIDC group claims in an enterprise
    plugin) but never narrow it.
    """
    if user.is_superuser or user.is_staff:
        return True

    if project.members.filter(id=user.id).exists():
        return True

    if project.group and project.group.administrators.filter(id=user.id).exists():
        return True

    from .extensions import get_permission_hooks
    for hook in get_permission_hooks('is_project_admin'):
        if hook(user, project) is True:
            return True

    return False
