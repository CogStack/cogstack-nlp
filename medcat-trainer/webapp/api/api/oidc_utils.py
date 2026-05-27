from django.contrib.auth import get_user_model
import secrets

from .extensions import user_oidc_resolved


def get_user_by_email(request, id_token):
    """
    Resolve or create a Django user from OIDC claims.

    Note: Some tokens (e.g. client-credentials / service-account tokens) may not
    include an email claim. In that case, fall back to a stable identifier so
    we don't violate DB NOT NULL constraints on the User model.
    """
    User = get_user_model()
    username = (
        id_token.get("preferred_username")
        or id_token.get("sub")
        or id_token.get("client_id")
        or f"oidc-{secrets.token_urlsafe(8)}"
    )
    email = id_token.get("email") or username
    roles = id_token.get('roles', [])
    is_superuser = 'medcattrainer_superuser' in roles
    is_staff = 'medcattrainer_staff' in roles

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "username": username,
            "email": email,
            "first_name": id_token.get("given_name", ""),
            "last_name": id_token.get("family_name", ""),
            "is_active": True,
            "password": secrets.token_urlsafe(32),
        },
    )

    user.username = username
    user.email = email
    user.first_name = id_token.get("given_name", "")
    user.last_name = id_token.get("family_name", "")
    user.is_superuser = is_superuser
    user.is_staff = is_staff

    user.save()

    user_oidc_resolved.send(
        sender=User,
        user=user,
        id_token=id_token,
        created=created,
    )
    return user
