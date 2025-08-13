#!/bin/sh

if [ -n "${DB_BACKUP_DIR}" ] && [ -f "${DB_PATH}" ]; then
  echo "Found backup dir location: ${DB_BACKUP_DIR} and DB_PATH: ${DB_PATH}"
  if [ ! -d "${DB_BACKUP_DIR}" ]; then
    mkdir DB_BACKUP_DIR
  else
    # remove backups older than 90 days.
    echo "Checking age of current backups - removing any older than 90 days.."
    find ${DB_BACKUP_DIR} -mtime +90 -type f -delete
  fi

  # Check if a backup already exists for today
  TODAY=$(date +"%Y-%m-%d")
  if [ -n "$(find ${DB_BACKUP_DIR} -name "db-backup-${TODAY}__*.sqlite3" -type f)" ]; then
    echo "A backup already exists for today (${TODAY}). Skipping backup creation."
    return 0
  fi

  BACKUP_NAME=db-backup-$(date +"%Y-%m-%d__%H-%M-%S").sqlite3
  cp $DB_PATH ${DB_BACKUP_DIR}/${BACKUP_NAME}
  echo "Backed up existing DB to ${DB_BACKUP_DIR}/${BACKUP_NAME}"
  echo "To restore this backup use $ /home/scripts/restore.sh ${DB_BACKUP_DIR}/${BACKUP_NAME}"
else
  echo "No DB_BACKUP_DIR env var found or DB_PATH . This should be set in env vars. No backups will be created"
  return 0
fi
