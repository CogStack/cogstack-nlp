# Installation

MedCATtrainer is packaged as a Docker Compose deployment with three core
services:

- `medcattrainer` (Django API + background workers)
- `nginx` (serves UI and proxies API)
- `solr` (concept search index for concept lookup)

## Prerequisites

- Docker Engine
- Docker Compose v2 (`docker compose` command)

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
| `MCTRAINER_PORT` | Host port for the web UI/API (default `8001`). |
| `SOLR_PORT` | Host port for Solr admin (default `8983`). |
| `MEDCAT_CONFIG_FILE` | MedCAT config file path inside the container. |
| `LOAD_EXAMPLES` | Load example model pack + dataset + project on startup (`1`/`0`). |
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
