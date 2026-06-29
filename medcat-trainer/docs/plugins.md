# Plugins & Extensions

MedCATtrainer can be extended with **enterprise / third-party plugins**. A plugin
is an ordinary Python package that is discovered at startup via the
`mct.plugins` [entry-point group](https://packaging.python.org/en/latest/specifications/entry-points/)
and installed as a Django app. Plugins can register backend hooks/signals and
contribute frontend menu items, routes, and UI slots.

This page describes **how plugins work** and, importantly, the **security/trust
model** you must understand before installing any plugin.

## Security & trust model

!!! danger "A plugin runs as fully-trusted, in-process application code"
    There is **no sandbox**. An installed `mct.plugins` package executes at
    import time and in `AppConfig.ready()` with the same privileges as
    MedCATtrainer itself. A plugin can read and write the entire database, read
    the filesystem and environment (including secrets), receive clinical
    document/annotation data via signals, register permission hooks that grant
    project-admin access, and expose new API endpoints.

    **Treat plugins like kernel modules: only install packages you trust and
    have reviewed.**

### What a plugin can do

| Capability | How |
| --- | --- |
| Run arbitrary code at startup | Module import + `AppConfig.ready()` |
| Read/write all application data | Django ORM access |
| Receive document/annotation/user data | Subscribing to `api.extensions` signals |
| Grant project-admin to users | `register_permission_hook('is_project_admin', ...)` |
| Add backend API endpoints | A plugin `urls.py` mounted at `/api/ee/<app_label>/` |
| Add frontend menu items / routes / UI | `register_menu_extension` / `register_route` / `PluginSlot` |

### What the scaffold guarantees (and does not)

The core app does not provide a security boundary to plugins, it does provide:

- **Grant-only permission hooks.** A hook returning `True` *grants* a
  permission; `None`/`False` abstains. Hooks **cannot revoke** access the OSS
  code already grants, so a plugin cannot lock legitimate users out.
- **URL validation.** `route`/`href`/`path` values registered for the frontend
  bootstrap are validated to be relative paths or `http(s)` URLs. Dangerous
  schemes (`javascript:`, `data:`, `vbscript:`, `file:` …) and
  protocol-relative (`//host`) values are rejected, so a plugin cannot inject a
  script-executing link into an authenticated user's browser.
- **Signal isolation.** Core signals are emitted with
  `api.extensions.dispatch()` (backed by `Signal.send_robust`). An exception in
  a plugin's receiver is logged and ignored — it cannot break document
  submission, annotation persistence, or OIDC login.

None of the above protects against a plugin that is *deliberately* malicious —
it already runs in-process. These measures only reduce the blast radius of
careless or buggy plugins.

### Operator guidance

- Only install plugins from sources you trust; review the code and pin exact
  versions/hashes (`pip install pkg==x.y.z --require-hashes`).
- Prefer building a dedicated image per deployment with a known, vetted set of
  plugins rather than installing plugins into a shared/long-lived environment.
- Be aware that plugins receiving annotation/document signals or the
  `user_oidc_resolved` `id_token` have access to potentially sensitive (PHI)
  data; ensure plugin authors handle it accordingly.

## How discovery works

1. A plugin package declares an entry point:

    ```toml
    # plugin's pyproject.toml
    [project.entry-points."mct.plugins"]
    my_plugin = "my_plugin.apps.MyPluginConfig"
    ```

2. The `AppConfig` opts in with `is_mct_plugin = True`:

    ```python
    # my_plugin/apps.py
    from django.apps import AppConfig

    class MyPluginConfig(AppConfig):
        name = "my_plugin"
        is_mct_plugin = True

        def ready(self):
            # Register hooks/signals here.
            from my_plugin import hooks  # noqa: F401
    ```

3. At startup `core.plugin_discovery` imports the `AppConfig`, verifies it is an
   `AppConfig` subclass with `is_mct_plugin = True`, and appends it to
   `INSTALLED_APPS`. If the plugin ships a `urls.py`, it is mounted at
   `/api/ee/<app_label>/`.

## Backend extension points

All backend extension points live in `api.extensions`. The module shape is
contract-tested, so these signatures are stable.

### Signals

Emitted by the core app; plugins connect receivers (in `AppConfig.ready()`):

| Signal | When | kwargs |
| --- | --- | --- |
| `pre_document_submit` / `post_document_submit` | around document submit | `project`, `document`, `user` |
| `annotation_created` / `annotation_updated` / `annotation_deleted` | annotation row change | `annotation`, `project`, `document`, (`user`) |
| `project_group_created` / `project_group_updated` | project group change | `project_group` |
| `user_oidc_resolved` | after OIDC user resolution | `user`, `id_token`, `created` |
| `model_pack_imported` | after `import_model_pack()` succeeds | `model_pack`, `user`, `description`, `source_uri` |

Receivers should be cheap and must not assume they can block the core flow —
exceptions are logged and swallowed.

### Permission hooks

```python
from api.extensions import register_permission_hook

def grant_from_oidc_group(user, project):
    # Return True to grant; None/False to abstain. Cannot deny.
    if user_in_admin_group(user):
        return True
    return None

register_permission_hook("is_project_admin", grant_from_oidc_group)
```

### Frontend bootstrap registries

```python
from api.extensions import register_feature, register_menu_extension, register_route

register_feature("adjudication")
register_menu_extension({"id": "adj", "label": "Adjudication", "route": "/ee/adj"})
register_route({"path": "/ee/adj", "component": "Adjudication"})
```

`route`/`href`/`path` must be relative paths or `http(s)` URLs; other schemes
raise `ValueError` at registration time.

### Model import

Plugins that pull model packs from an external registry (e.g. MedCATtery) should
use the stable helper rather than re-implementing upload/unpack:

```python
from api.model_import import ImportModelPackError, import_model_pack

try:
    model_pack = import_model_pack(
        "/tmp/snomed_v3.zip",
        name="snomed-v3",
        user=request.user,
        description="Imported from MedCATtery",
        source_uri="https://medcattery.example/models/snomed/3",
    )
except ImportModelPackError as exc:
    ...
```

`import_model_pack` creates a `ModelPack` (and linked `ConceptDB` / `Vocabulary`
via the normal `ModelPack.save()` path) and emits `model_pack_imported`.
Annotation projects reference `model_pack.id`, not the CDB directly.

## Backend API endpoints — required auth pattern

Plugin URLs are mounted on the **same origin** as the core app under
`/api/ee/<app_label>/`. The scaffold does **not** add authentication for you —
**every plugin view must enforce its own authentication and authorisation.**

Use DRF's `IsAuthenticated` at minimum, and reuse `api.permissions.is_project_admin`
for project-scoped operations:

```python
# my_plugin/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("adjudication/<int:project_id>/", views.adjudication_summary),
]
```

```python
# my_plugin/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions
from rest_framework.response import Response

from api.models import ProjectAnnotateEntities
from api.permissions import is_project_admin


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])  # REQUIRED: no anonymous access
def adjudication_summary(request, project_id):
    try:
        project = ProjectAnnotateEntities.objects.get(id=project_id)
    except ProjectAnnotateEntities.DoesNotExist:
        return Response({"error": "Project not found"}, status=404)

    # REQUIRED for project-scoped data: enforce project-admin access.
    if not is_project_admin(request.user, project):
        return Response({"error": "Forbidden"}, status=403)

    return Response({"project": project.id, "summary": "..."})
```

!!! warning "Do not expose unauthenticated endpoints"
    Because plugin routes share the trainer's origin and session/token context,
    an endpoint that omits `permission_classes([IsAuthenticated])` is reachable
    by anyone who can reach the trainer. Always gate views explicitly, and add
    project-level checks with `is_project_admin` for any project-scoped data.

## Frontend extension points

- **Menu items** registered via `register_menu_extension` appear in the top nav.
- **Routes** are added either at build time (a bundled Vue plugin calling
  `registerPlugin({ routes: [...] })`) or described via `register_route` for the
  bootstrap payload.
- **UI slots** let a build-time plugin inject components at named slots, e.g.
  `home:after-projects`, `project-admin:tabs`, `project-admin:modelpacks`,
  `train-annotations:sidebar`:

    ```ts
    import { registerPlugin } from "@/plugins/registry";
    registerPlugin({ slots: { "home:after-projects": MyWidget } });
    ```

Build-time frontend plugins are bundled into the SPA and are therefore also
fully trusted; the same "only ship code you trust" rule applies.
