#!/usr/bin/env bash
set -euo pipefail

secret_name="${1:?Uso: rotate-secret.sh SECRET_NAME ENV_VAR [vercel-key]}"
source_variable="${2:?Indica la variable de entorno que contiene el valor nuevo}"
vercel_key="${3:-}"
: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"

secret_value="${!source_variable:-}"
if [[ -z "${secret_value}" ]]; then
  echo "Error: ${source_variable} está vacía." >&2
  exit 1
fi

printf '%s' "${secret_value}" | gcloud secrets versions add "${secret_name}" \
  --project "${GCP_PROJECT_ID}" --data-file=- >/dev/null

if [[ -n "${vercel_key}" ]]; then
  : "${VERCEL_TOKEN:?Define VERCEL_TOKEN para rotar también el BFF}"
  printf '%s' "${secret_value}" | pnpm dlx vercel@58.0.0 env add \
    "${vercel_key}" staging --force --token="${VERCEL_TOKEN}" >/dev/null
fi

unset secret_value
echo "Nueva versión creada sin imprimir el valor. Redespliega y deshabilita la versión anterior tras verificar."
