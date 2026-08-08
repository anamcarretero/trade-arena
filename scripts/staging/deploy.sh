#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"
: "${GCP_REGION:=europe-west3}"
: "${BACKEND_IMAGE:?Define BACKEND_IMAGE con digest OCI}"
: "${VERCEL_TOKEN:?Define VERCEL_TOKEN}"
: "${VERCEL_ORG_ID:?Define VERCEL_ORG_ID}"
: "${VERCEL_PROJECT_ID:?Define VERCEL_PROJECT_ID}"

case "${BACKEND_IMAGE}" in
  *@sha256:*) ;;
  *) echo "Error: BACKEND_IMAGE debe estar fijada por digest sha256." >&2; exit 1 ;;
esac

gcloud run jobs update tradearena-migrate-staging \
  --project "${GCP_PROJECT_ID}" --region "${GCP_REGION}" --image "${BACKEND_IMAGE}" --quiet
gcloud run jobs execute tradearena-migrate-staging \
  --project "${GCP_PROJECT_ID}" --region "${GCP_REGION}" --wait

gcloud run services update tradearena-api-staging \
  --project "${GCP_PROJECT_ID}" --region "${GCP_REGION}" --image "${BACKEND_IMAGE}" --quiet
api_url="$(gcloud run services describe tradearena-api-staging \
  --project "${GCP_PROJECT_ID}" --region "${GCP_REGION}" --format='value(status.url)')"
"${repository_dir}/scripts/verify-deployment.sh" "${api_url}"

export VERCEL_ORG_ID VERCEL_PROJECT_ID
pnpm --dir "${repository_dir}/web" dlx vercel@58.0.0 pull \
  --yes --environment=staging --token="${VERCEL_TOKEN}"
web_url="$(pnpm --dir "${repository_dir}/web" dlx vercel@58.0.0 deploy \
  --yes --target=staging --token="${VERCEL_TOKEN}")"

"${repository_dir}/scripts/verify-deployment.sh" "${api_url}" "${web_url}"
echo "Staging verificado: API ${api_url}; PWA ${web_url}"
