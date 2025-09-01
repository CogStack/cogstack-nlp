# Maintanence

MedCATtrainer is actively maintained. To ensure you receive the latest
security patches of the software and its dependencies you should regularly
be upgrading to the latest release.

The latest stable releases update the `docker-compose.yml` and `docker-compose-prod.yml` files.

To update these docker compose files, either copy them directly from the [repo](https://github.com/CogStack/cogstack-nlp/tree/main/medcat-trainer)
or update the cloned files via:

```shell
$ cd MedCATtrainer
$ git pull
$ docker-compose up
# alternatively for prod releases use:
$ docker-compose -f docker-compose-prod.yml up
```

MedCATtrainer follows [Semver](https://semver.org/), so patch and minor release should always be backwards compatible, 
whereas major releases, e.g. v1.x vs 2.x versions signify breaking changes. 

Neccessary Django DB migrations will automatically applied between releases, which should largely be invisible to an end admin 
or annotation user. Nevertheless, migrating ORM / DB models, then rolling back a release can cause issues if values are defaulted 
or removed from a later version. 

## Backup and Restore

### Backup
Before updating to a new release, a backup will be created in the `DB_BACKUP_DIR`, as configured in `envs/env`.
A further crontab runs the same backup script at 10pm every night. This does not cause any downtime and will look like
this in the logs:
```shell
medcattrainer-medcattrainer-db-backup-1  | Found backup dir location: /home/api/db-backup and DB_PATH: /home/api/db/db.sqlite3
medcattrainer-medcattrainer-db-backup-1  | Backed up existing DB to /home/api/db-backup/db-backup-2023-09-26__23-26-01.sqlite3
medcattrainer-medcattrainer-db-backup-1  | To restore this backup use $ ./restore.sh /home/api/db-backup/db-backup-2023-09-26__23-26-01.sqlite3
```

A backup is also automatically performed each time the service starts, and any migrations are performed, in the events of a new release
introducing a breaking change and corrupting a DB.

### Restore
If a DB is corrupted or needs to be restored to an existing backed up db use the following commands, whilst the service is running:

```shell
$ docker ps
CONTAINER ID   IMAGE                                          COMMAND                  CREATED      STATUS      PORTS                                               NAMES
a2489b0c681b   cogstacksystems/medcat-trainer-nginx:v2.11.2   "/docker-entrypoint.…"   4 days ago   Up 4 days   80/tcp, 0.0.0.0:8001->8000/tcp, :::8001->8000/tcp   medcattrainer-nginx-1
20fed153d798   solr:8                                         "docker-entrypoint.s…"   4 days ago   Up 4 days   0.0.0.0:8983->8983/tcp, :::8983->8983/tcp           mct_solr
2b250a0975fe   cogstacksystems/medcat-trainer:v2.11.2         "/home/run.sh"           4 days ago   Up 4 days                                                       medcattrainer-medcattrainer-1
$ docker exec -it 2b250a0975fe bash
root@2b250a0975fe:/home/api# cd ..
$ restore_db.sh db-backup-2023-09-25__23-21-39.sqlite3  # run the restore.sh script
Found backup dir location: /home/api/db-backup, found db path: home/api/db/db.sqlite3
DB file to restore: db-backup-2023-09-25__23-21-39.sqlite3
Found db-backup-2023-09-25__23-21-39.sqlite3 - y to confirm backup: y  # you'll need tp confirm this is the correct file to restore.
Restored db-backup-2023-09-25__23-21-39.sqlite3 to /home/db/db.sqlite3
```

The `restore_db.sh` script will automatically restore the latest db file, if no file is specified.

