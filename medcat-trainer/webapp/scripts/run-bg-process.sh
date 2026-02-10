#!/bin/sh

# Use uv-managed project environment (no manual venv activation)
export UV_PROJECT=/home

# env vars that should only be on for app running...
export RESUBMIT_ALL_ON_STARTUP=0

# Collect static files and migrate if needed
uv run python /home/api/manage.py collectstatic --noinput
uv run python /home/api/manage.py makemigrations --noinput
uv run python /home/api/manage.py makemigrations api --noinput
uv run python /home/api/manage.py migrate --noinput
uv run python /home/api/manage.py migrate api --noinput

uv run python /home/api/manage.py process_tasks --log-std
