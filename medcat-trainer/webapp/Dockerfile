# -----------------------------------------------------------------------------
# Stage 1: Build frontend assets (Node toolchain discarded after this stage)
# -----------------------------------------------------------------------------
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline --no-audit --no-fund

COPY frontend/ ./
# CI test-frontend already runs type-check; build-only avoids a second vue-tsc pass.
# No sourcemaps in the image — saves ~25MB+ and build I/O.
RUN NODE_OPTIONS=--max-old-space-size=4096 \
    npm run build-only -- --sourcemap false

# -----------------------------------------------------------------------------
# Stage 2: Install Python deps (Rust/build tools discarded after this stage)
# -----------------------------------------------------------------------------
FROM python:3.12-bookworm AS python-builder

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends build-essential curl && \
    rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /home
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    pip install --no-cache-dir uv && \
    uv sync --frozen --cache-dir=/root/.cache/uv --no-install-project --extra observability

RUN uv run python -m ensurepip --upgrade

ARG SPACY_MODELS="en_core_web_md"
RUN for SPACY_MODEL in ${SPACY_MODELS}; do uv run python -m spacy download ${SPACY_MODEL}; done

# -----------------------------------------------------------------------------
# Stage 3: Runtime image — no Node, npm, Rust, or frontend devDependencies
# -----------------------------------------------------------------------------
FROM python:3.12-bookworm

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        vim \
        supervisor \
        gettext \
        cron \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /etc/cron.*/*

RUN pip install --no-cache-dir uv

WORKDIR /home
COPY pyproject.toml uv.lock ./
COPY --from=python-builder /home/.venv /home/.venv
COPY api ./api
COPY scripts ./scripts
COPY templates ./templates
COPY --from=frontend-builder /build/dist ./frontend/dist

# MEDIA_ROOT is a runtime volume; ensure the directory exists without baking in local uploads
RUN mkdir -p /home/api/media

RUN chmod u+x /home/scripts/entry.sh && \
    chmod u+x /home/scripts/crontab && cp /home/scripts/crontab /etc/crontab && \
    chmod a+x /home/scripts/run.sh && \
    chmod a+x /home/scripts/run-bg-process.sh && \
    chmod a+x /home/scripts/nginx-entrypoint.sh

WORKDIR /home/api/
