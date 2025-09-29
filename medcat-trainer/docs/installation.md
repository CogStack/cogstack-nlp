# Installation
MedCATtrainer is a docker-compose packaged Django application.

## Download from Dockerhub
Clone the repo, run the default docker-compose file and default env var:
```shell
$ git clone https://github.com/CogStack/cogstack-nlp
$ cd cogstack-nlp/medcat-trainer
$ docker-compose up
```

This will use the pre-built docker images available on DockerHub. If your internal firewall does on permit access to DockerHub, you can build directly from source.

To check logs of the MedCATtrainer running containers
```bash
$  docker logs <containerid> | grep "\[medcattrainer\]"
$  docker logs <containerid> | grep "\[bg-process\]"
$  docker logs <containerid> | grep "\[db-backup\]"
```

## MedCAT v0.x models
If you have MedCAT v0.x models, and want to use the trainer please use the following docker-compose file:
This refences the latest built image for the trainer that is still compatible with [MedCAT v0.x.](https://pypi.org/project/medcat/0.4.0.6/) and under.
```shell
$ docker-compose -f docker-compose-mc0x.yml up
```

## Build images from source
The above commands runs the latest release of MedCATtrainer, if you'd prefer to build the Docker images from source, use
```shell
$ docker-compose -f docker-compose-dev.yml up
```

To change environment variables, such as the exposed host ports and language of spaCy model, use:
```shell
$ cp .env-example .env
# Set local configuration in .env
```

## Troubleshooting
If the build fails with an error code 137, the virtual machine running the docker
daemon does not have enough memory. Increase the allocated memory to containers in the docker daemon
settings CLI or associated docker GUI.

On MAC: https://docs.docker.com/docker-for-mac/#memory

On Windows: https://docs.docker.com/docker-for-windows/#resources

### (Optional) SMTP Setup

For password resets and other emailing services email environment variables are required to be set up.

Personal email accounts can be set up by users to do this, or you can contact someone in CogStack for a cogstack no email credentials.

The environment variables required are listed in [Environment Variables.](#(optional)-environment-variables)

Environment Variables are located in envs/env or envs/env-prod, when those are set webapp/frontend/.env must change "VITE_APP_EMAIL" to 1.

### (Optional) Environment Variables
Environment variables are used to configure the app:

|Parameter|Description|
|---------|-----------|
|MEDCAT_CONFIG_FILE|MedCAT config file as described [here](https://github.com/CogStack/cogstack-nlp/blob/main/medcat-v2/medcat/config/config.py)|
|BEHIND_RP| If you're running MedCATtrainer, use 1, otherwise this defaults to 0 i.e. False|
|MCTRAINER_PORT|The port to run the trainer app on|
|EMAIL_USER|Email address which will be used to send users emails regarding password resets|
|EMAIL_PASS|The password or authentication key which will be used with the email address|
|EMAIL_HOST|The hostname of the SMTP server which will be used to send email (default: mail.cogstack.org)|
|EMAIL_PORT|The port that the SMTP server is listening to, common numbers are 25, 465, 587 (default: 465)|

Set these and re-run the docker-compose file.

You'll need to `docker stop` the running containers if you have already run the install.

### (Optional) Postgres Database Support
MedCAT trainer defaults to a local SQLite database, which is suitable for single-user or small-scale setups.  

For larger deployments, or to support multiple replicas of the app for example in Kubernetes, you may want to run a postgresql database.

You can optionally use a postgresql database instead by setting the following env variables. 

|Parameter|Description|
|---------|-----------|
|DB_ENGINE|Database engine to use. Either `sqlite3` or `postgresql`. Defaults to `sqlite3` if not set.|
|DB_NAME|Name of the database to connect to.|
|DB_USER|Username to authenticate with the database.|
|DB_PASSWORD|Password to authenticate with the database.|
|DB_HOST|Hostname of the database server (for Postgres, typically the service name in Docker/Kubernetes).|
|DB_PORT|Port the database server is listening on. Defaults to `5432` for Postgres.|