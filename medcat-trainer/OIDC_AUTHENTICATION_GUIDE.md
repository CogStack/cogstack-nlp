# OIDC Authentication in MedCAT Trainer

## Overview

MedCAT Trainer supports OpenID Connect (OIDC) authentication via Keycloak, allowing users to log in with centralized credentials instead of managing separate accounts.

### What is OIDC?

OpenID Connect is an authentication protocol built on top of OAuth 2.0 that allows applications to verify user identity through a trusted identity provider (like Keycloak).

**Key Concepts:**
- **Identity Provider (IdP)**: Keycloak server that manages user authentication
- **Client**: MedCAT Trainer (the application requesting authentication)
- **Token**: A signed JWT (JSON Web Token) that proves user identity
- **Realm**: A Keycloak namespace containing users, roles, and clients

---

## Architecture

MedCAT Trainer uses a **two-client architecture** for OIDC:

### 1. Frontend Public Client (`cogstack-medcattrainer-frontend`)

**Purpose:** Browser-based authentication flow

**Type:** Public client (no secret, code runs in browser)

**Responsibilities:**
- Redirects user to Keycloak login page
- Receives authentication token
- Includes token in API requests

**Configuration:**
// Frontend config (loaded at runtime)
```json
{
  "USE_OIDC": "1",
  "KEYCLOAK_URL": "https://auth.cogstack.example.site",
  "KEYCLOAK_REALM": "cogstack",
  "KEYCLOAK_CLIENT_ID": "cogstack-medcattrainer-frontend",
  "KEYCLOAK_LOGOUT_REDIRECT_URI": "https://launchpad.cogstack.example.site/"
}
```

### 2. Backend Confidential Client (`cogstack-medcattrainer-backend`)

**Purpose:** Server-side token validation

**Type:** Confidential client (has secret, runs on server)

**Responsibilities:**
- Validates tokens from frontend
- Extracts user information and roles
- Creates/updates Django users

**Configuration:**
```python
# Backend settings
KEYCLOAK_INTERNAL_SERVICE_URL = "https://auth.cogstack.example.site"
KEYCLOAK_REALM = "cogstack"
KEYCLOAK_FRONTEND_CLIENT_ID = "cogstack-medcattrainer-frontend"
KEYCLOAK_BACKEND_CLIENT_ID = "cogstack-medcattrainer-backend"
KEYCLOAK_BACKEND_CLIENT_SECRET = "***secret***"
```
---
## Key Files

### Frontend

| File | Purpose |
|------|---------|
| `src/runtimeConfig.ts` | Loads and provides runtime config |
| `src/auth.ts` | Keycloak initialization and setup |
| `src/main.ts` | App bootstrap, conditionally loads OIDC |
| `src/App.vue` | Handles login/logout, shows username |
| `public/config.template.json` | Template for runtime config |

### Backend

| File | Purpose |
|------|---------|
| `api/core/settings.py` | OIDC configuration and DRF setup |
| `api/api/oidc_utils.py` | User creation/update from token |
| `scripts/nginx-entrypoint.sh` | Runtime config generation |
| `scripts/run.sh` | Startup script (runs nginx-entrypoint.sh) |

---

## User Lifecycle

### First Login

1. User logs in via Keycloak
2. Token generated with user info
3. Backend receives token
4. `get_user_by_email()` called
5. Django user created:
   ```python
   User.objects.get_or_create(
       email='john@cogstack.org',
       defaults={
           "username": "johndoe",
           "first_name": "John",
           "last_name": "Doe",
           "is_active": True,
           "password": secrets.token_urlsafe(32),  # Random, unused
           "is_superuser": False,  # Set based on roles
           "is_staff": False,
       }
   )
   ```

### Subsequent Logins

1. User logs in via Keycloak
2. Token generated
3. Backend finds existing user by email
4. Updates user information:
   ```python
   user.username = token['preferred_username']
   user.first_name = token['given_name']
   user.last_name = token['family_name']
   user.is_superuser = 'medcattrainer_superuser' in roles
   user.is_staff = 'medcattrainer_staff' in roles
   user.save()
   ```

### Role Changes

If a user's Keycloak roles change:
1. User logs out
2. User logs back in
3. New token includes updated roles
4. Backend updates Django user permissions
5. User immediately has new access level

---

## Troubleshooting

### User sees old login form instead of Keycloak

**Symptoms:**
- Old username/password form appears
- No redirect to Keycloak

**Causes:**
1. Runtime config not loaded
2. `USE_OIDC` not set to `1`
3. Frontend failed to load `/static/config.json`

**Solutions:**
```bash
# Check config exists
curl http://medcattrainer.../static/config.json

# Check environment variables
docker exec <container> env | grep VITE_USE_OIDC

# Check logs
docker logs <container> | grep "RuntimeConfig"
```

### API returns 401 Unauthorized

**Symptoms:**
- Login works but API calls fail
- Browser console shows 401 errors
- Keycloak logs: "Token is not active"

**Causes:**
1. Backend not accepting frontend client ID in audience
2. Token expired
3. Token signature invalid

**Solutions:**
```bash
# Check OIDC_FRONTEND_CLIENT_ID is set
docker exec <container> env | grep OIDC_FRONTEND_CLIENT_ID

# Check backend logs for audience claims
docker logs <container> | grep "Accepted audience claims"

# Should show: account, backend-client-id, frontend-client-id
```

### User has no permissions after login

**Symptoms:**
- Login successful
- User sees no projects
- Not a superuser/staff

**Causes:**
1. Keycloak roles not mapped
2. Backend not reading roles from correct location in token
3. User needs role assigned in Keycloak

**Solutions:**
```bash
# Check user in database
docker exec <container> python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(email='user@example.com')
print(f'is_superuser: {user.is_superuser}')
print(f'is_staff: {user.is_staff}')
"

# Check token includes roles
# Look in backend logs for printed id_token

# Assign role in Keycloak:
# Users → Select user → Role mapping → Assign role
```

### Token validation fails

**Symptoms:**
- "Invalid token" errors
- "Signature verification failed"

**Causes:**
1. Keycloak public key changed
2. Wrong OIDC_HOST configuration

**Solutions:**
```bash
# Verify OIDC_HOST matches Keycloak
docker exec <container> env | grep OIDC_HOST

# Check Keycloak is reachable from container
docker exec <container> curl -I <OIDC_HOST>/realms/<REALM>

# Restart container to refresh public keys
docker restart <container>
```

---

## Testing OIDC Locally

### Prerequisites

1. Running Keycloak instance
2. Realm configured (`cogstack-realm`)
3. Two clients created:
   - `cogstack-medcattrainer-frontend` (public)
   - `cogstack-medcattrainer-backend` (confidential with secret)
4. Realm roles:
   - `medcattrainer_superuser`
   - `medcattrainer_staff`
5. Test user with assigned roles

### Local Configuration

```bash
# envs/env
USE_OIDC=1
OIDC_HOST=http://keycloak:8080
OIDC_REALM=cogstack-realm
OIDC_FRONTEND_CLIENT_ID=cogstack-medcattrainer-frontend
OIDC_BACKEND_CLIENT_ID=cogstack-medcattrainer-backend
OIDC_BACKEND_CLIENT_SECRET=your-secret-here

VITE_USE_OIDC=1
VITE_KEYCLOAK_URL=http://keycloak.cogstack.localhost/
VITE_KEYCLOAK_REALM=cogstack-realm
VITE_KEYCLOAK_CLIENT_ID=cogstack-medcattrainer-frontend
VITE_LOGOUT_REDIRECT_URI=http://home.cogstack.localhost/
```

### Test Flow

1. Start services:
   ```bash
   docker-compose -f docker-compose-dev.yml up
   ```

2. Visit `http://medcattrainer.cogstack.localhost`

3. Should redirect to Keycloak login

4. Login with test user

5. Should redirect back and show MedCAT Trainer with username in header

6. Check browser console (F12):
   ```
   [RuntimeConfig] OIDC enabled: true
   [Bootstrap] OIDC mode enabled
   ```

7. Check backend logs:
   ```bash
   docker logs medcat-trainer-medcattrainer-1 | grep OIDC
   # Should show: "Using OIDC authentication"
   # Should show: "Accepted audience claims: ..."
   ```

---

## References

- [OpenID Connect Specification](https://openid.net/specs/openid-connect-core-1_0.html)
- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [Django REST Framework Token Authentication](https://www.django-rest-framework.org/api-guide/authentication/)
- [drf-oidc-auth](https://github.com/ByteInternet/drf-oidc-auth)
