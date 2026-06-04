# MedCAT Service

Medcat service is a REST API for serving [MedCAT](https://github.com/CogStack/cogstack-nlp/blob/main/medcat-v2/) models, allowing you to send text for processing and receive structured annotations in response.

See the documentation on https://docs.cogstack.org/ for the docs on medcat service.

This README file contains information for local usage and devloper guides.

## Running the application

The application can be run either as a standalone Python application or as running inside the Docker container (recommended).

## Running as a Python app

Please note that prior running the application a number of requirements need to installed (see: `requirements.txt`).

There are two scripts provided implementing starting the application:

- `start_service_debug.sh` - starts the application in the development mode
- `start_service_production.sh` - starts the application in 'production' mode and using `gunicorn` server.

## Running in a Docker container

The recommended way to run the application is to use the provided Docker image. The Docker image can be either downloaded from the Docker Hub (`cogstacksystems/medcat-service:latest`) or build manually using the provided `Dockerfile`.
Please note that by default the built docker image will run the Flask application in 'production' mode running `start_service_production.sh` script.

To build the Docker image manually:

`docker build -t medcat-service  .`

To run the container using the built image:

```bash
  docker run -it -p 5000:5000 \
    --env-file=envs/env_app --env-file=envs/env_medcat \
    -v <models-local-dir>:/cat/models:ro \
    cogstacksystems/medcat-service:latest
```

By default the MedCAT service will be running on port `5000`. MedCAT models will be mounted from local directory `<models-local-dir>` into the container at `/cat/models`.

### GPU support

If you have a gpu and wish to use it, please change the `docker/docker-compose.yml` file, use the `cogstacksystems/medcat-service-gpu:latest` image or change the `build:` directive to build `../Dockerfile_gpu`.

### IMPORTANT

If you wish to run this docker service manually, use the docker/docker-compose.yml file, execute `docker compose up -d` whilst in the `docker` folder.

Alternatively, an example script `./docker/run_example_medmen.sh` was provided to run the Docker container with MedCAT service. The script will download an example model (using the `./scripts/download_medmen.sh` script),it will use an example environment configuration, then it will build and start the service using the provided Docker Compose file, the service ***WONT WORK*** without the model being present.

All models should be mounted from the `models/` folder.

### Manual docker start-up steps

```bash
  1. cd ./models/
  2. bash ./download_medmen.sh
  3. cd ../docker/
  4. docker compose up -d
  5. echo "DONE!"
```

Or, if you wish to use the above mentioned script ( the sample model is downloaded via script, you don't need to do anything):

```bash
  1. cd ./docker/
  2. bash ./run_example_medmen.sh
  DONE!
```


## Local Env Configuration

In the current implementation, configuration for both MedCAT Service application and MedCAT NLP library is based on environment variables. These will be provided usually in the files in the `env` directory:

- `env/(app|app_deid).env` - configuration of MedCAT Service app,
- `env/(medcat|medcat_deid).env` - configuration of MedCAT library.
- `env/general.env` - configuration of general DOCKER related variables, CPU architecture, shared memory size etc, this is part of all of the major services services across CogStack, also set in the master repo in NiFi.

Both files allow tailoring MedCAT for specific use-cases. When running MedCAT Service, these variables need to be loaded into the current working environment.

## Local development

For local development, set up a Python virtual environment, install dependencies with pip, and make sure to also install the local MedCAT core library (the `medcat-v2` folder) in editable mode. 

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
SETUPTOOLS_SCM_PRETEND_VERSION="2.4.0-dev0" pip install -e "../medcat-v2[meta-cat,spacy]"
bash start_service_debug.sh

# Service will run on localhost:8000
```