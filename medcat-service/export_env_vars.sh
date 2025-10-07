#!/usr/bin/env bash

# Enable strict mode (without -e to avoid exit-on-error)
set -uo pipefail


echo "🔧 Running $(basename "${BASH_SOURCE[0]}")..."

set -a

current_dir=$(pwd)

env_files=("env/general.env"
           "env/app.env"
           "env/medcat.env"
           )


for env_file in "${env_files[@]}"; do
  if [ -f "$env_file" ]; then
    echo "✅ Sourcing $env_file"
    # shellcheck disable=SC1090
    source "$env_file"
  else
    echo "⚠️ Skipping missing env file: $env_file"
  fi
done


# Disable auto-export
set +a

# Restore safe defaults for interactive/dev shell
set +u
set +o pipefail
