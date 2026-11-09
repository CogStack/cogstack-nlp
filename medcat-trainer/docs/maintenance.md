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
- Document text search: each uploaded dataset is indexed into the Solr collection
  `DOCUMENT_SEARCH_COLLECTION` (default `medcattrainer_documents`) by a background task
  when `DOCUMENT_SEARCH_INDEX_ENABLED=1`. Datasets uploaded before this was available
  can be indexed via the Django admin Datasets action
  "Index selected datasets for text search" (see [Django Admin](django_admin.md)).
  Until a dataset is fully indexed, or if Solr is unavailable, text search falls back
  to a slower database match. Annotators use **Name** / **Text** modes in the Clinical
  Notes panel — see [Annotator Guide](annotator_guide.md#searching-clinical-notes).

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

