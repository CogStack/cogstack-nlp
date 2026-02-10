#!/bin/sh

# Use venv where uv installed dependencies (explicit path)
PY=/home/.venv/bin/python

# env vars that should only be on for app running...
export RESUBMIT_ALL_ON_STARTUP=0

# Collect static files and migrate if needed
"$PY" /home/api/manage.py collectstatic --noinput
"$PY" /home/api/manage.py makemigrations --noinput
"$PY" /home/api/manage.py makemigrations api --noinput
"$PY" /home/api/manage.py migrate --noinput
"$PY" /home/api/manage.py migrate api --noinput

"$PY" /home/api/manage.py process_tasks --log-std
