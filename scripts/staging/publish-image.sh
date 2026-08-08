#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
: "${GCP_PROJECT_ID:?Define GCP_PROJECT_ID}"
: "${GCP_REGION:=europe-west3}"

registry="${GCP_REGION}-docker.pkg.dev"
tag="${registry}/${GCP_PROJECT_ID}/tradearena/api:bootstrap"
gcloud auth configure-docker "${registry}" --quiet
docker build --file "${repository_dir}/Dockerfile" --tag "${tag}" "${repository_dir}"
docker push "${tag}"
digest="$(docker inspect --format='{{index .RepoDigests 0}}' "${tag}")"
case "${digest}" in
  *@sha256:*) printf '%s\n' "${digest}" ;;
  *) echo "Error: no se pudo resolver el digest publicado." >&2; exit 1 ;;
esac
