# Administrator Setup

This page covers first-login admin hardening and user setup.

## 1) Configure bootstrap admin credentials

Before first startup in production-like environments, set:

- `MCTRAINER_BOOTSTRAP_ADMIN_USERNAME`
- `MCTRAINER_BOOTSTRAP_ADMIN_EMAIL`
- `MCTRAINER_BOOTSTRAP_ADMIN_PASSWORD`

If not set, MedCATtrainer defaults to `admin` / `admin`, which is not suitable
for production.

## 2) Sign in

Staff and superuser accounts see a cog icon at the top-right of the header.
That opens **Project Administration** (`/project-admin`), used to set up
users, datasets, model packs, projects, and project groups. See
[Project Administration](project_admin.md).

Django Admin (`/admin`) remains the place for full platform administration,
including passwords and actions this screen does not cover.

Create at least one dedicated administrator and grant:

- `Staff status`, so the account can open the cog icon
- `Superuser status`, for unrestricted access, including Django admin

## 3) Create annotator users

Add annotators from the **Users** tab on Project Administration, then add
them to a project or project group. Annotators do not need staff or
superuser flags.

The password field on that form is not stored. Set each password in Django
admin (`/admin` -> **Users**), or through the password-reset flow, before
the person signs in.

## 4) Remove or rotate bootstrap credentials

After creating named administrator accounts:

- remove the default bootstrap account if it is no longer needed, or
- rotate its password and store credentials securely.

## 5) If using OIDC

When `USE_OIDC=1`, user permissions are mapped from IdP roles:

- `medcattrainer_superuser` -> Django superuser + staff. This role shows the cog icon.
- `medcattrainer_staff` -> Django staff. This role does not show the cog icon.

Ensure role assignment is correct in Keycloak before onboarding users.
