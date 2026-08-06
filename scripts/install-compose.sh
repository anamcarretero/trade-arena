#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_dir="$(cd "${script_dir}/.." && pwd)"
env_file="${repository_dir}/.env"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: Docker con Compose es obligatorio." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Error: el motor Docker no está arrancado." >&2
  exit 1
fi

if [[ ! -f "${env_file}" ]]; then
  echo "Error: falta .env. Copia .env.example a .env y cambia la contraseña." >&2
  exit 1
fi

password="$(sed -n 's/^POSTGRES_PASSWORD=//p' "${env_file}" | tail -n 1)"
if [[ -z "${password}" || "${password}" == replace-* ]]; then
  echo "Error: sustituye POSTGRES_PASSWORD por un secreto URL-safe en .env." >&2
  exit 1
fi

for variable in AUTH0_DOMAIN AUTH0_CLIENT_ID AUTH0_CLIENT_SECRET BFF_SHARED_SECRET SESSION_ENCRYPTION_KEY; do
  value="$(sed -n "s/^${variable}=//p" "${env_file}" | tail -n 1)"
  if [[ -z "${value}" || "${value}" == replace-* ]]; then
    echo "Error: define ${variable} con un valor real en .env." >&2
    exit 1
  fi
done

docker compose \
  --project-directory "${repository_dir}" \
  --env-file "${env_file}" \
  --file "${repository_dir}/compose.yaml" \
  config --quiet

docker compose \
  --project-directory "${repository_dir}" \
  --env-file "${env_file}" \
  --file "${repository_dir}/compose.yaml" \
  build api web

docker compose \
  --project-directory "${repository_dir}" \
  --env-file "${env_file}" \
  --file "${repository_dir}/compose.yaml" \
  up --detach --no-build

port="$(sed -n 's/^TRADEARENA_PORT=//p' "${env_file}" | tail -n 1)"
web_port="$(sed -n 's/^TRADEARENA_WEB_PORT=//p' "${env_file}" | tail -n 1)"
"${script_dir}/verify-deployment.sh" \
  "http://127.0.0.1:${port:-8080}" "http://127.0.0.1:${web_port:-3000}"
