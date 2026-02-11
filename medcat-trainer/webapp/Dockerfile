FROM python:3.11

# Update and upgrade everything
RUN apt-get update -y && \
    apt-get upgrade -y

# install vim as its annoying not to have an editor
RUN apt-get install -y vim

# install supervisor
RUN apt-get install -y supervisor

# install gettext for envsubst (used to generate runtime config)
RUN apt-get install -y gettext

# install cron - and remove any default tabs
RUN apt-get install -y cron && which cron && rm -rf /etc/cron.*/*

# Get node and npm
RUN apt install -y nodejs && apt install -y npm

# Install Rust - for tokenziers dep in medcat.
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy dependency files first for better layer caching
WORKDIR /home/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install

# Install Python dependencies
WORKDIR /home
COPY requirements.txt ./
RUN pip install pip --upgrade 
RUN pip install "setuptools>=81.0.0,<82"
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy models (only requires spaCy, not application code)
ARG SPACY_MODELS="en_core_web_md"
RUN for SPACY_MODEL in ${SPACY_MODELS}; do python -m spacy download ${SPACY_MODEL}; done

# Copy rest of project
WORKDIR /home
COPY ./ .

# Build frontend
WORKDIR /home/frontend
RUN npm run build

# copy backup crontab and chmod scripts
RUN chmod u+x /home/scripts/entry.sh && \
    chmod u+x /home/scripts/crontab && cp /home/scripts/crontab /etc/crontab && \
    chmod a+x /home/scripts/run.sh && \
    chmod a+x /home/scripts/run-bg-process.sh && \
    chmod u+x /home/scripts/nginx-entrypoint.sh
 
WORKDIR /home/api/

