#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"
: "${GCP_REGION:=europe-west3}"
: "${PREVIOUS_BACKEND_IMAGE:?Define el digest backend anterior compatible}"
: "${PREVIOUS_VERCEL_DEPLOYMENT:?Define URL o ID del deployment staging anterior}"
: "${VERCEL_TOKEN:?Define VERCEL_TOKEN}"

case "${PREVIOUS_BACKEND_IMAGE}" in
  *@sha256:*) ;;
  *) echo "Error: el rollback de API exige un digest sha256." >&2; exit 1 ;;
esac

# No se revierte SQL. Solo es seguro si el binario anterior tolera el esquema
# expandido; una contracción se entrega en un cambio posterior.
gcloud run services update tradearena-api-staging \
  --project "${GCP_PROJECT_ID}" --region "${GCP_REGION}" \
  --image "${PREVIOUS_BACKEND_IMAGE}" --quiet
pnpm dlx vercel@58.0.0 redeploy "${PREVIOUS_VERCEL_DEPLOYMENT}" \
  --target=staging --token="${VERCEL_TOKEN}" >/dev/null
echo "API y PWA revertidas. El esquema compatible permanece en su versión avanzada."
