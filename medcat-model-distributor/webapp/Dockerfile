# Stage 1: Build stage (dependencies and compilation)
FROM python:3.12-slim AS build

# Create the required folders
RUN mkdir -p /webapp/models

# Copy the application code
COPY . /webapp

# Install dependencies for building (git, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    apt-utils \
    cron \
    sqlite3 \
    libsqlite3-dev


RUN pip install -U pip && pip install -r /webapp/requirements.txt

# Stage 2: Final (production) image
FROM python:3.12-slim AS final

# Install runtime dependencies (you don’t need git in production)
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    sqlite3 \
    libsqlite3-dev && apt-get autoremove

# Create the required folders (if not created already)
RUN mkdir -p /webapp/models && mkdir -p /medcat_data

# Copy only necessary files from build stage
COPY --from=build /webapp /webapp
# COPY --from=build /root/.cache /root/.cache  # Copy pip cache if needed

# Copy Python site-packages (installed by pip) from build stage
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Set the pythonpath
WORKDIR /webapp

# Create the db backup cron job (copied from your setup)
COPY etc/cron.d/db-backup-cron /etc/cron.d/db-backup-cron
RUN chmod 0644 /etc/cron.d/db-backup-cron && crontab /etc/cron.d/db-backup-cron

# Run collect static (could be in entrypoint script)
RUN python manage.py collectstatic --noinput

# setup entrypoint
COPY entrypoint.sh /webapp/entrypoint.sh
RUN chmod +x /webapp/entrypoint.sh
# this does migration and cron job
ENTRYPOINT ["/webapp/entrypoint.sh"]
# and then, finally runs the (flexible) runserver command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
