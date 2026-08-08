#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"
: "${GCP_REGION:=europe-west3}"

gcloud run services describe tradearena-api-staging \
  --project "${GCP_PROJECT_ID}" --region "${GCP_REGION}" \
  --format='table(status.url,status.latestReadyRevision,status.conditions.type,status.conditions.status)'
gcloud run jobs executions list --job tradearena-migrate-staging \
  --project "${GCP_PROJECT_ID}" --region "${GCP_REGION}" --limit=5
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="tradearena-api-staging"' \
  --project "${GCP_PROJECT_ID}" --limit=20 --freshness=1h \
  --format='table(timestamp,severity,textPayload)'
