# Maintenance

Keep MedCATtrainer regularly updated to receive dependency and security fixes.

## Upgrade workflow

```bash
cd medcat-trainer
git pull
docker compose pull
docker compose up -d
```

For production compose:

```bash
docker compose -f docker-compose-prod.yml pull
docker compose -f docker-compose-prod.yml up -d
```

Database migrations are applied automatically on container startup.

## Operational checks

- Application/API health: `GET /api/health/`
- Container logs: `docker compose logs -f medcattrainer`
- Concept search availability: verify Solr container and project concept import
  status.

## Backup and restore (SQLite deployments)

The backup scripts are SQLite-focused (`DB_ENGINE=sqlite3`).

### Automatic backups

- A backup is taken on startup before migrations.
- A scheduled backup job also runs regularly.
- Backup location is controlled by:
  - `DB_PATH`
  - `DB_BACKUP_DIR`

### Restore process

1. Enter the running `medcattrainer` container.
2. Run restore script:

```bash
/home/scripts/restore_db.sh <backup-file-name>
```

If no filename is provided, the latest backup is selected.

The script prompts for confirmation before overwriting the active DB.

## Release compatibility

MedCATtrainer follows semantic versioning:

- patch/minor versions are expected to be backward compatible,
- major versions may include breaking changes.

Avoid rollback after schema migrations unless you have tested rollback
procedures and verified data compatibility.

