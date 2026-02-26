# Administrator Setup

This page covers first-login admin hardening and user setup.

## 1) Configure bootstrap admin credentials

Before first startup in production-like environments, set:

- `MCTRAINER_BOOTSTRAP_ADMIN_USERNAME`
- `MCTRAINER_BOOTSTRAP_ADMIN_EMAIL`
- `MCTRAINER_BOOTSTRAP_ADMIN_PASSWORD`

If not set, MedCATtrainer defaults to `admin` / `admin`, which is not suitable
for production.

## 2) Sign in and create operational admin users

You can manage users from:

- **Project Admin UI** (`/project-admin`) for day-to-day project operations
- **Django Admin** (`/admin`) for full platform administration

In Django admin (`/admin`), create at least one dedicated administrator account
and grant:

- `Staff status` for admin access
- `Superuser status` for full unrestricted access

## 3) Create annotator users

Create users for annotators and add them to project membership lists.
Annotators do not need staff/superuser flags.

## 4) Remove or rotate bootstrap credentials

After creating named administrator accounts:

- remove the default bootstrap account if it is no longer needed, or
- rotate its password and store credentials securely.

## 5) If using OIDC

When `USE_OIDC=1`, user permissions are mapped from IdP roles:

- `medcattrainer_superuser` -> Django superuser + staff
- `medcattrainer_staff` -> Django staff

Ensure role assignment is correct in Keycloak before onboarding users.
