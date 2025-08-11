#!/bin/sh

CURR_LOC=$(pwd)
mkdir -p /tmp/mc_trainer/envs
cd /tmp/mc_trainer
DOCKER_COMP_FILE=dc.yml
ENV_FILE=/tmp/mc_trainer/envs/env

echo "Downloading docker-compose.yml and default env vars"
curl https://raw.githubusercontent.com/CogStack/cogstack-nlp/09e32429/medcat-trainer/docker-compose.yml > $DOCKER_COMP_FILE
curl https://raw.githubusercontent.com/CogStack/cogstack-nlp/09e32429/medcat-trainer/envs/env > $ENV_FILE
trap 'rm -rf /tmp/mc_trainer && cd $CURR_LOC' EXIT

echo "Starting MedCATtrainer containers"
#ls -l
nohup docker-compose -f $DOCKER_COMP_FILE up &>/dev/null &
while true;
do
  sleep 5
  IS_READY=$(curl http://localhost:8001 -w "%{http_code}" -Isl | head -n1 | cut -d ' ' -f2)
  if [ "$IS_READY" = "200" ]; then
    break
  else
    echo "Loading..."
    docker-compose -f $DOCKER_COMP_FILE logs
  fi
done
echo \
"\n---------------------------------------------------------\n"\
"---- MedCATtrainer running on http://localhost:8001/ ----\n"\
"---------------------------------------------------------\n"