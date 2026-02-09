#!/bin/sh
echo "Starting medcat trainer"

# run db backup script before doing anything
/home/scripts/backup_db.sh

# env vars that should only be on for app running...
TMP_RESUBMIT_ALL_VAR=$RESUBMIT_ALL_ON_STARTUP
export RESUBMIT_ALL_ON_STARTUP=0

# Collect static files and migrate if needed
python /home/api/manage.py collectstatic --noinput
python /home/api/manage.py makemigrations --noinput
python /home/api/manage.py makemigrations api --noinput
python /home/api/manage.py migrate --noinput
python /home/api/manage.py migrate api --noinput

# Generates the runtime configuration for the web app and copies it to the static directory for web access
/home/scripts/nginx-entrypoint.sh

# create a new super user, with configurable username, email, and password via env vars
# also create a user group `user_group` that prevents users from deleting models
echo "import os
from django.contrib.auth import get_user_model
User = get_user_model()
admin_username = os.getenv('MCTRAINER_BOOTSTRAP_ADMIN_USERNAME') or 'admin'
admin_email = os.getenv('MCTRAINER_BOOTSTRAP_ADMIN_EMAIL') or 'admin@example.com'
admin_password = os.getenv('MCTRAINER_BOOTSTRAP_ADMIN_PASSWORD') or 'admin'
if not User.objects.filter(username=admin_username).exists():
    User.objects.create_superuser(admin_username, admin_email, admin_password)
" | python manage.py shell

if [ $LOAD_EXAMPLES ]; then 
  echo "Loading examples..."
  python /home/scripts/load_examples.py >> /dev/stdout 2>> /dev/stderr &
fi

# Creating a default user group that can manage projects and annotate but not delete
python manage.py shell < /home/scripts/create_group.py

# RESET any Env vars to original stat
export RESUBMIT_ALL_ON_STARTUP=$TMP_RESUBMIT_ALL_VAR

uwsgi --http-timeout 360s --http :8000 --master --chdir /home/api/  --module core.wsgi
