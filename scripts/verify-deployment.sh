#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-http://127.0.0.1:8080}"
attempts="${VERIFY_ATTEMPTS:-30}"

if ! command -v curl >/dev/null 2>&1; then
  echo "Error: curl es obligatorio para verificar el despliegue." >&2
  exit 1
fi

for path in /health/live /health/ready /openapi.json; do
  ready=false
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl --fail --silent --show-error "${base_url}${path}" >/dev/null; then
      ready=true
      break
    fi
    sleep 1
  done
  if [[ "${ready}" != true ]]; then
    echo "Error: ${base_url}${path} no respondió tras ${attempts} intentos." >&2
    exit 1
  fi
  echo "OK ${base_url}${path}"
done
