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
  "KEYCLOAK_URL": "https://cogstack-auth.sites.er.kcl.ac.uk",
  "KEYCLOAK_REALM": "cogstack",
  "KEYCLOAK_CLIENT_ID": "cogstack-medcattrainer-frontend",
  "LOGOUT_REDIRECT_URI": "https://cogstack-launchpad.sites.er.kcl.ac.uk/"
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
OIDC_HOST = "https://cogstack-auth.sites.er.kcl.ac.uk"
OIDC_REALM = "cogstack"
OIDC_FRONTEND_CLIENT_ID = "cogstack-medcattrainer-frontend"
OIDC_BACKEND_CLIENT_ID = "cogstack-medcattrainer-backend"
OIDC_BACKEND_CLIENT_SECRET = "***secret***"
```

---

## Authentication Flow

### Step-by-Step Process

```
┌──────────┐                 ┌──────────────┐                 ┌──────────┐
│  User    │                 │   Keycloak   │                 │ MedCAT   │
│ Browser  │                 │  (Identity   │                 │ Trainer  │
│          │                 │   Provider)  │                 │ Backend  │
└──────────┘                 └──────────────┘                 └──────────┘
     │                               │                               │
     │ 1. Visit MedCATtrainer        │                               │
     ├──────────────────────────────────────────────────────────────>│
     │                               │                               │
     │ 2. Redirect to Keycloak login │                               │
     │<──────────────────────────────────────────────────────────────┤
     │                               │                               │
     │ 3. Show login page            │                               │
     ├──────────────────────────────>│                               │
     │                               │                               │
     │ 4. Enter credentials          │                               │
     ├──────────────────────────────>│                               │
     │                               │                               │
     │ 5. Validate & generate token  │                               │
     │<──────────────────────────────┤                               │
     │                               │                               │
     │ 6. Redirect back with token   │                               │
     │<──────────────────────────────┤                               │
     │                               │                               │
     │ 7. API request with token     │                               │
     ├──────────────────────────────────────────────────────────────>│
     │                               │                               │
     │                               │ 8. Validate token             │
     │                               │<──────────────────────────────┤
     │                               │                               │
     │                               │ 9. Token valid + user info    │
     │                               │──────────────────────────────>│
     │                               │                               │
     │                               │    10. Create/update user     │
     │                               │        Extract roles          │
     │                               │                               │
     │ 11. Return API response       │                               │
     │<──────────────────────────────────────────────────────────────┤
```

### Detailed Steps

1. **User visits MedCAT Trainer**
   - Frontend loads `/static/config.json` to check if OIDC is enabled
   - If `USE_OIDC=1`, initializes Keycloak adapter

2. **Redirect to Keycloak**
   - Frontend redirects to: `https://keycloak.../realms/cogstack/protocol/openid-connect/auth`
   - Includes: client ID, redirect URI, scopes

3. **User authenticates**
   - Keycloak shows login page
   - User enters username/password
   - Keycloak validates credentials

4. **Token generation**
   - Keycloak generates ID token, access token, refresh token
   - Tokens contain user info (email, name, roles)

5. **Redirect back to app**
   - Keycloak redirects to: `http://medcattrainer.../`
   - Includes authorization code in URL

6. **Token exchange**
   - Frontend exchanges code for tokens
   - Stores tokens in browser memory (not localStorage for security)

7. **API requests**
   - Frontend includes token in `Authorization: Bearer <token>` header
   - Every API call includes this header

8. **Backend validates token**
   - Django REST Framework receives request
   - `BearerTokenAuthentication` extracts token
   - Validates token signature using Keycloak's public key
   - Checks token expiration and audience claims

9. **User creation/update**
   - `oidc_utils.get_user_by_email()` called
   - Extracts user info from token
   - Creates Django user if new, updates if existing
   - Applies roles (superuser/staff based on Keycloak roles)

10. **Request processed**
    - User authenticated and authorized
    - API endpoint processes request
    - Returns response

---

## Configuration

### Environment Variables

#### Frontend (Runtime Config - `/static/config.json`)

| Variable | Example | Description |
|----------|---------|-------------|
| `VITE_USE_OIDC` | `1` | Enable OIDC (1=enabled, 0=traditional auth) |
| `VITE_KEYCLOAK_URL` | `https://cogstack-auth.sites.er.kcl.ac.uk` | Keycloak base URL |
| `VITE_KEYCLOAK_REALM` | `cogstack` | Keycloak realm name |
| `VITE_KEYCLOAK_CLIENT_ID` | `cogstack-medcattrainer-frontend` | Public client ID |
| `VITE_LOGOUT_REDIRECT_URI` | `https://cogstack-launchpad.sites.er.kcl.ac.uk/` | Where to go after logout |

#### Backend (Django Settings)

| Variable | Example | Description |
|----------|---------|-------------|
| `USE_OIDC` | `1` | Enable OIDC validation |
| `OIDC_HOST` | `https://cogstack-auth.sites.er.kcl.ac.uk` | Keycloak base URL (for backend) |
| `OIDC_REALM` | `cogstack` | Realm name |
| `OIDC_FRONTEND_CLIENT_ID` | `cogstack-medcattrainer-frontend` | Frontend client ID (for token validation) |
| `OIDC_BACKEND_CLIENT_ID` | `cogstack-medcattrainer-backend` | Backend client ID |
| `OIDC_BACKEND_CLIENT_SECRET` | `***secret***` | Backend client secret |

### Runtime Configuration Generation

The frontend configuration is generated at container startup:

1. **Template**: `/home/frontend/dist/config.template.json`
   ```json
   {
     "USE_OIDC": "${VITE_USE_OIDC}",
     "KEYCLOAK_URL": "${VITE_KEYCLOAK_URL}",
     ...
   }
   ```

2. **Script**: `/home/scripts/nginx-entrypoint.sh`
   - Validates required environment variables
   - Substitutes values using `envsubst`
   - Generates `/home/api/static/config.json`

3. **Frontend loads**: Fetches `/static/config.json` at startup
   ```javascript
   // main.ts
   await loadRuntimeConfig();
   if (isOidcEnabled()) {
     await authPlugin.install(app);
   }
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

## Role Mapping

### Keycloak Roles → Django Permissions

The backend checks for specific Keycloak realm roles and maps them to Django permissions:

```python
# In oidc_utils.py
roles = id_token.get('roles', [])

is_superuser = 'medcattrainer_superuser' in roles
is_staff = 'medcattrainer_staff' in roles
```

| Keycloak Role | Django Permission | Capabilities |
|---------------|-------------------|--------------|
| `medcattrainer_superuser` | `is_superuser=True`, `is_staff=True` | Full admin access, Django admin, all projects |
| `medcattrainer_staff` | `is_staff=True` | Staff-level access, can manage assigned projects |
| (no role) | Regular user | Can only access assigned projects, no admin |

### Token Structure

Example token payload:
```json
{
  "sub": "c924cc03-c1d4-444c-a6ba-2f0553438a14",
  "email": "jocelyne@cogstack.org",
  "email_verified": false,
  "name": "Jocelyne Holdbrook",
  "preferred_username": "jocelyneholdbrook",
  "given_name": "Jocelyne",
  "family_name": "Holdbrook",
  "roles": [
    "medcattrainer_superuser",
    "medcattrainer_staff",
    "default-roles-cogstack-realm",
    "offline_access",
    "uma_authorization"
  ],
  "group_memberships": [
    "/medcattery-users",
    "/medcattrainer-users"
  ],
  "aud": ["account", "cogstack-medcattrainer-frontend"],
  "iss": "https://cogstack-auth.sites.er.kcl.ac.uk/realms/cogstack"
}
```

---

## Token Validation

### Backend Token Validation Process

1. **Extract token** from `Authorization: Bearer <token>` header

2. **Verify signature**
   - Fetch Keycloak's public keys from `/.well-known/jwks.json`
   - Verify JWT signature using public key

3. **Validate claims**
   ```python
   # settings.py
   'OIDC_CLAIMS_OPTIONS': {
       'aud': {
           'values': [
               'account',
               'cogstack-medcattrainer-backend',
               'cogstack-medcattrainer-frontend'  # ← Important!
           ],
           'essential': True,
       },
       'iss': {
           'values': [
               'https://cogstack-auth.../realms/cogstack'
           ],
           'essential': True,
       },
   }
   ```

4. **Check expiration**
   - Tokens have `exp` claim (typically 5-15 minutes)
   - Expired tokens are rejected

5. **Resolve user**
   - Call `oidc_utils.get_user_by_email()`
   - Create or update Django user
   - Apply roles

### Why Frontend Client ID Must Be in Audience

The frontend client obtains the token, so the token's `aud` (audience) claim contains `cogstack-medcattrainer-frontend`. The backend must accept this audience, otherwise validation fails with "Token is not active" error.

This is why `OIDC_FRONTEND_CLIENT_ID` is **required** in backend settings.

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
       email='jocelyne@cogstack.org',
       defaults={
           "username": "jocelyneholdbrook",
           "first_name": "Jocelyne",
           "last_name": "Holdbrook",
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

## Security Considerations

### Token Storage

- ✅ **Good**: Frontend stores tokens in memory (Keycloak adapter default)
- ❌ **Bad**: Don't store in localStorage (vulnerable to XSS)

### Token Transmission

- ✅ All communication over HTTPS in production
- ✅ Tokens included in `Authorization` header (not URL)
- ✅ Tokens have short expiration (refresh automatically)

### Audience Validation

The backend validates the `aud` claim to ensure tokens are intended for this application:

```python
'aud': {
    'values': [
        'account',
        'cogstack-medcattrainer-backend',
        'cogstack-medcattrainer-frontend'  # Tokens from frontend client
    ],
    'essential': True,
}
```

### CORS and CSRF

- OIDC flow uses redirects, not AJAX, avoiding CORS issues
- Django CSRF protection disabled for OIDC endpoints
- Token validation provides sufficient security

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
1. Clock skew between servers
2. Keycloak public key changed
3. Wrong OIDC_HOST configuration

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

## Comparison: Traditional Auth vs OIDC

| Feature | Traditional Auth | OIDC Auth |
|---------|------------------|-----------|
| User storage | Django database | Keycloak (centralized) |
| Password management | Per-app | Centralized in Keycloak |
| Login UI | Custom form in app | Keycloak-hosted |
| Single Sign-On | No | Yes (across all apps) |
| Role management | Django admin | Keycloak admin |
| Password reset | Email-based | Keycloak handles |
| 2FA/MFA | Manual implementation | Keycloak built-in |
| Audit logging | Limited | Full Keycloak audit |

---

## References

- [OpenID Connect Specification](https://openid.net/specs/openid-connect-core-1_0.html)
- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [Django REST Framework Token Authentication](https://www.django-rest-framework.org/api-guide/authentication/)
- [mozilla-django-oidc](https://mozilla-django-oidc.readthedocs.io/) (similar library for reference)
