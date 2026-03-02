#!/bin/bash
set -e

python manage.py migrate --noinput
/etc/init.d/cron start || echo "cron failed, continuing"
exec "$@"