#!/bin/sh

DB_RESTORE_FILE=$1
BACKUP_DIR=${DB_BACKUP_DIR}

if [ -n "$BACKUP_DIR" ] && [ -n "$DB_PATH" ]; then
    echo "Found backup dir location: ${BACKUP_DIR}, found db path: ${DB_PATH}"
    if [ -z "$DB_RESTORE_FILE" ]; then
      echo "No specific backup specified. Restoring latest backup in $BACKUP_DIR"
      DB_RESTORE_FILE=$(ls -Art ${BACKUP_DIR}/ | tail -n 1)
    fi
    echo "DB file to restore: ${DB_RESTORE_FILE}"
    read -p "Found $DB_RESTORE_FILE - y to confirm backup: " choice
    case "$choice" in
      y|Y )
        cp $BACKUP_DIR/$DB_RESTORE_FILE $DB_PATH
        echo "Restored $DB_RESTORE_FILE to $DB_PATH"
        ;;
      n|N )
        echo " - exiting";;
      * )
        echo "Invalid choice - exiting";;
    esac
  else
    echo "No BACKUP_DIR and DB_PATH found. Set to location of the backups and the location of DB sqlite3 file to be restored."
fi
