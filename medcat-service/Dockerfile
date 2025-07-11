FROM python:3.11-slim

ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1

# Set the python path and preapre the base layer
WORKDIR /cat
COPY ./requirements.txt /cat

# Install Python dependencies
ARG USE_CPU_TORCH=true
# NOTE: Allow building without GPU so as to lower image size (GPU is disabled by default)
RUN pip install -U pip && \
    if [ "${USE_CPU_TORCH}" = "true" ]; then \
        echo "Installing Torch for CPU, without GPU support " && \
        pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu/; \
    else \
        echo "Installing Torch with GPU support" && \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# Get the spacy model
ARG SPACY_MODELS="en_core_web_sm en_core_web_md en_core_web_lg"
RUN for spacy_model in $SPACY_MODELS; do python -m spacy download $spacy_model; done

# Copy the remaining files
COPY . /cat

# NOTE: for test/CI time, this will install medcat based on local path
ARG REINSTALL_CORE_FROM_LOCAL=false
RUN if [ "$REINSTALL_CORE_FROM_LOCAL" = "true" ]; then \
        echo "Reinstalling medcat based on relative path"; \
        pip install -e "./medcat-v2[meta-cat,spacy]"; \
    fi

# Now run the simple api
CMD ["/bin/bash", "start_service_production.sh"]
