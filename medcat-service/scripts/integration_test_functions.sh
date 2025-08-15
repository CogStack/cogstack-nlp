smoketest_medcat_service() {
    local localhost_name="$1"
    local docker_compose_file="$2"
    local port=${3:-5555}
    if [ -z "$localhost_name" ] || [ -z "$docker_compose_file" ]; then
        echo "Invalid arguments. Usage: health_check <localhost_name> <docker_compose_file>" >&2
        return 1
    fi

    API="http://${localhost_name}:${port}/api/info"

    MAX_RETRIES=12
    RETRY_DELAY=5
    COUNT=0

    while [ $COUNT -lt $MAX_RETRIES ]; do
    echo "Checking service health on $API (Attempt $((COUNT+1))/$MAX_RETRIES)"
    sleep $RETRY_DELAY
    IS_READY=$(curl -s -o /dev/null -w "%{http_code}" $API)
    
    if [ "$IS_READY" = "200" ]; then
        echo "Service is ready!"
        break
    else
        echo "Attempt $((COUNT+1))/$MAX_RETRIES: Not ready (HTTP $IS_READY)."
        docker compose -f ${DOCKER_COMPOSE_FILE} logs
        COUNT=$((COUNT+1))
    fi
    done

    if [ $COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Service did not become ready after $MAX_RETRIES attempts."
    exit 1
    fi

    echo "Service passed basic smoke test"

}


integration_test_medcat_service() {
  local localhost_name=$1
  local port=${2:-5555}
  local expected_annotation=${3:-Kidney Failure}

  # Test /api/process
  local api="http://${localhost_name}:${port}/api/process"
  local input_text="Patient J. Smith had been diagnosed with acute kidney failure the week before"
  local input_payload="{\"content\":{\"text\":\"${input_text}\"}}"

  echo "Calling POST $api with payload '$input_payload'"
  local actual

  actual=$(curl -s -X POST $api \
    -H 'Content-Type: application/json' \
    -d "$input_payload")

  echo "Recieved result '$actual'"

  local actual_annotation
  actual_annotation=$(echo "$actual" | jq -r '.result.annotations[0]["0"].pretty_name')

  if [[ "$actual_annotation" == "$expected_annotation" ]]; then
    echo "Service working and extracting annotations for Process API"
  else
    echo "Expected: $expected_annotation, Got: $actual_annotation"
    echo -e "Actual response was:\n${actual}"
    return 1
  fi

  # Test /api/process_bulk

  if [[ "$expected_annotation" == "PATIENT" ]]; then
     echo "Skipping Process_bulk test for DeID Mode testing "
     echo "Process_bulk in DeID mode appears to have a bug making it return the text without deid"
     return 0
  fi

  local api="http://${localhost_name}:${port}/api/process_bulk"
  local input_text="Patient J. Smith had been diagnosed with acute kidney failure the week before"
  local input_payload="{\"content\": [{\"text\":\"${input_text}\"}]}"
  local expected_annotation="Kidney Failure"


  echo "Calling POST $api with payload '$input_payload'"
  local actual

  actual=$(curl -s -X POST $api \
    -H 'Content-Type: application/json' \
    -d "$input_payload")

  echo "Recieved result '$actual'"

  local actual_annotation
  actual_annotation=$(echo "$actual" | jq -r '.result[0].annotations[0]["0"].pretty_name')

  if [[ "$actual_annotation" == "$expected_annotation" ]]; then
    echo "Service working and extracting annotations for Process Bulk API"
  else
    echo "Expected: $expected_annotation, Got: $actual_annotation"
    echo -e "Actual response was:\n${actual}"
    return 1
  fi

}
