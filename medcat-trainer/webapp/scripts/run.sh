#!/bin/sh

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

# create a new super user, with username and password 'admin'
# also create a user group `user_group` that prevents users from deleting models
echo "from django.contrib.auth import get_user_model
User = get_user_model()
if User.objects.count() == 0:
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
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
