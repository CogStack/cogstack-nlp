from django.contrib.auth import get_user_model
import secrets

def get_user_by_email(request, id_token):
    """
    Resolve or create a Django user using the email claim from OIDC.
    """
    User = get_user_model()
    email = id_token.get('email')
    username = id_token.get('preferred_username')
    print(id_token)
    roles = []
    if 'realm_access' in id_token:
        roles = id_token['realm_access'].get('roles', [])

    is_superuser = 'medcattrainer_superuser' in roles
    is_staff = 'medcattrainer_staff' in roles

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "username": username,
            "first_name": id_token.get("given_name", ""),
            "last_name": id_token.get("family_name", ""),
            "is_active": True,
            "password": secrets.token_urlsafe(32),
        },
    )

    user.username = username
    user.first_name = id_token.get("given_name", "")
    user.last_name = id_token.get("family_name", "")
    user.is_superuser = is_superuser
    user.is_staff = is_staff

    user.save()
    return user
