#!/bin/sh

# env vars that should only be on for app running...
export RESUBMIT_ALL_ON_STARTUP=0

# Collect static files and migrate if needed
python /home/api/manage.py collectstatic --noinput
python /home/api/manage.py makemigrations --noinput
python /home/api/manage.py makemigrations api --noinput
python /home/api/manage.py migrate --noinput
python /home/api/manage.py migrate api --noinput

python /home/api/manage.py process_tasks --log-std
