import secrets
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

def get_user_by_email(request, id_token):
    """
    Resolve or create a Django user using the email claim from OIDC.
    If the user does not exist, create one with a random, opaque password.
    """
    User = get_user_model()
    email = id_token.get("email")

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "username": id_token.get("preferred_username") or email,
            "first_name": id_token.get("given_name", ""),
            "last_name": id_token.get("family_name", ""),
            "is_active": True,
            # Generate a random opaque password (hashed)
            "password": make_password(secrets.token_urlsafe(32)),
        },
    )

    return user
