# Installation

The steps to setup Medcat trainer are as follows:

1. Run MedCAT Trainer with Docker or Helm
2. Setup the Administrator user with [Administrator Setup](admin_setup.md) 
3. Configure annotations Projects

This page details the initial running of the application with Docker

MedCATtrainer is packaged as a Docker Compose deployment with three core
services:

- `medcattrainer` (Django API + background workers)
- `nginx` (serves UI and proxies API)
- `solr` (concept search index for concept lookup)

## Prerequisites

- Docker Engine
- Docker Compose v2 (`docker compose` command)
- `uv` (only needed for the local Django debug script)

## Quick start (prebuilt images)

```bash
git clone https://github.com/CogStack/cogstack-nlp
cd cogstack-nlp/medcat-trainer
docker compose up -d
```

Open the app at `http://localhost:8001` (unless you changed `MCTRAINER_PORT`).

Useful logs:

```bash
docker compose logs -f medcattrainer
docker compose logs -f nginx
docker compose logs -f solr
```

## Build from source (development)

```bash
docker compose -f docker-compose-dev.yml up --build
```

This uses the local `webapp/` source tree and is the recommended setup for
development work.

### Local Django debug script

For backend development where you want to run Django directly on your host
machine, use the local debug helper:

```bash
./webapp/scripts/run_local_debug.sh
```

The script sources `envs/env`, syncs Python dependencies with `uv` when needed,
runs migrations, creates a local admin user, ensures the default user group
exists, and starts Django at `http://127.0.0.1:8001/`.

By default it also starts only the `solr` service with Docker Compose:

```bash
docker compose -f docker-compose-dev.yml up -d solr
```

Before starting Solr, the script ensures the Compose gateway network exists. It
uses `gateway-auth_gateway-net` by default, creating it if it is missing. If you
are running MedCATtrainer alongside a different gateway stack, set the network
name explicitly:

```bash
MCT_GATEWAY_NETWORK_NAME=my-gateway-net ./webapp/scripts/run_local_debug.sh
```

Available modes:

```bash
./webapp/scripts/run_local_debug.sh server
./webapp/scripts/run_local_debug.sh worker
./webapp/scripts/run_local_debug.sh shell
./webapp/scripts/run_local_debug.sh bootstrap
```

Common overrides:

| Variable | Description |
|---|---|
| `MCT_DEBUG_HOST` | Django bind host (default `0.0.0.0`). |
| `MCT_DEBUG_PORT` | Django port (default `8001`). |
| `MCT_ENV_FILE` | Env file to source instead of `envs/env`. |
| `MCT_ADMIN_USERNAME` | Local admin username (default `admin`). |
| `MCT_ADMIN_PASSWORD` | Local admin password (default `admin`). |
| `MCT_START_SOLR` | Start Solr through Docker Compose (`1`/`0`, default `1`). |
| `MCT_GATEWAY_NETWORK_NAME` | External Compose network to use/create for Solr. |
| `MCT_SYNC_DEPS` | Run `uv sync --frozen` (`1`/`0`/`auto`, default `auto`). |

## Legacy MedCAT v0.x support

If you still need the legacy MedCAT v0.x-compatible stack:

```bash
docker compose -f docker-compose-mc0x.yml up -d
```

## Environment configuration

Runtime settings are mainly defined in:

- `envs/env` (non-prod defaults)
- `envs/env-prod` (production-oriented defaults)

Host-level Compose variables (for example port overrides) can be set by copying
`.env-example` to `.env` and editing values.

### Common environment variables

| Variable | Description |
|---|---|
| `CSRF_TRUSTED_ORIGINS` | Allowed origins to access the admin panel. Mandatory to set if you expose the app over a different URL or port (default `'http://127.0.0.1:8001', 'http://localhost:8001'`). |
| `MCTRAINER_PORT` | Host port for the web UI/API (default `8001`). |
| `SOLR_PORT` | Host port for Solr admin (default `8983`). |
| `MEDCAT_CONFIG_FILE` | MedCAT config file path inside the container. |
| `LOAD_EXAMPLES` | Load example model pack + dataset + project on startup (`1`/`0`). |
| `PROVISIONING_CONFIG_PATH` | File path of a yaml defining projects to create on startup |
| `REMOTE_MODEL_SERVICE_TIMEOUT` | Timeout (seconds) for remote model-service calls. |
| `MCTRAINER_BOOTSTRAP_ADMIN_USERNAME` | Bootstrap admin username (default `admin`). |
| `MCTRAINER_BOOTSTRAP_ADMIN_EMAIL` | Bootstrap admin email. |
| `MCTRAINER_BOOTSTRAP_ADMIN_PASSWORD` | Bootstrap admin password (change in real deployments). |

### SMTP (optional, for password reset emails)

Set:

- `EMAIL_USER`
- `EMAIL_PASS`
- `EMAIL_HOST`
- `EMAIL_PORT`

If SMTP is not configured, password reset workflows will fail.

## OIDC (Keycloak) authentication (optional)

Set `USE_OIDC=1` and provide:

| Variable | Description |
|---|---|
| `KEYCLOAK_URL` | Public Keycloak URL (frontend redirect/login). |
| `KEYCLOAK_REALM` | Keycloak realm name. |
| `KEYCLOAK_LOGOUT_REDIRECT_URI` | URL to redirect users to on logout. |
| `KEYCLOAK_INTERNAL_SERVICE_URL` | Backend-reachable Keycloak URL. |
| `KEYCLOAK_FRONTEND_CLIENT_ID` | Public frontend client ID. |
| `KEYCLOAK_BACKEND_CLIENT_ID` | Confidential backend client ID. |
| `KEYCLOAK_BACKEND_CLIENT_SECRET` | Backend client secret. |

Optional token refresh tuning:

- `KEYCLOAK_TOKEN_MIN_VALIDITY` (default `30`)
- `KEYCLOAK_TOKEN_REFRESH_INTERVAL` (default `20`)

Role mapping:

- `medcattrainer_superuser` -> Django superuser/staff
- `medcattrainer_staff` -> Django staff

## PostgreSQL support (optional)

SQLite is default. For larger deployments, set:

| Variable | Description |
|---|---|
| `DB_ENGINE` | `sqlite3` or `postgresql` |
| `DB_NAME` | Database name |
| `DB_USER` | Database user |
| `DB_PASSWORD` | Database password |
| `DB_HOST` | Database host/service |
| `DB_PORT` | Database port (default `5432`) |

An example compose file is available at
`docker-compose-example-postgres.yml`.

## Troubleshooting

- **Exit code 137 during build/start**: container memory is too low.
  Increase Docker memory allocation.
- **Cannot log in with default admin**: verify bootstrap admin env vars and
  startup logs.
- **Concept picker empty**: confirm Solr is running and concepts were imported
  for the selected CDB.

## Next Steps
Now that medcat trainer is installed and running, proceed to [Administrator Setup](admin_setup.md) to create the Admin user.


<!-- LRTEST_MARKER_123 -->
