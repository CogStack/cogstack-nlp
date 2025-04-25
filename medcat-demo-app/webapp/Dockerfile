# Stage 1: Build stage (dependencies and compilation)
FROM python:3.11-slim as build

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

# Install Python dependencies
RUN pip install -U pip && pip install -r /webapp/requirements.txt

# Get the spacy model (for later copy)
RUN python -m spacy download en_core_web_md

# Stage 2: Final (production) image
FROM python:3.11-slim as final

# Install runtime dependencies (you don’t need git in production)
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    sqlite3 \
    libsqlite3-dev

# Create the required folders (if not created already)
RUN mkdir -p /webapp/models && mkdir -p /medcat_data

# Copy only necessary files from build stage
COPY --from=build /webapp /webapp
COPY --from=build /root/.cache /root/.cache

# Set environment variables
ENV VOCAB_URL=https://medcat.rosalind.kcl.ac.uk/media/vocab.dat
ENV CDB_URL=https://medcat.rosalind.kcl.ac.uk/media/cdb-medmen-v1.dat

ENV CDB_PATH=/webapp/models/cdb.dat
ENV VOCAB_PATH=/webapp/models/vocab.dat

# Set the pythonpath
WORKDIR /webapp

# Create the db backup cron job (copied from your setup)
COPY etc/cron.d/db-backup-cron /etc/cron.d/db-backup-cron
RUN chmod 0644 /etc/cron.d/db-backup-cron && crontab /etc/cron.d/db-backup-cron

# Run migrations and collect static (could be in entrypoint script)
RUN python manage.py makemigrations && \
    python manage.py makemigrations demo && \
    python manage.py migrate && \
    python manage.py migrate demo && \
    python manage.py collectstatic --noinput
