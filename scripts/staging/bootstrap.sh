#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
infra_dir="${repository_dir}/infra/staging"
mode="${1:-plan}"

for command in terraform gcloud; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "Error: falta ${command}." >&2
    exit 1
  fi
done

if [[ ! -f "${infra_dir}/terraform.tfvars" ]]; then
  echo "Error: copia terraform.tfvars.example a terraform.tfvars y completa valores no secretos." >&2
  exit 1
fi

terraform -chdir="${infra_dir}" fmt -check -recursive
terraform -chdir="${infra_dir}" init
terraform -chdir="${infra_dir}" validate
terraform -chdir="${infra_dir}" plan -out=staging.tfplan

if [[ "${mode}" == "plan" ]]; then
  echo "Plan guardado en infra/staging/staging.tfplan; no se creó ningún recurso."
  exit 0
fi
if [[ "${mode}" != "apply" || "${CONFIRM_STAGING_APPLY:-}" != "TA-039-STAGING" ]]; then
  echo "Error: apply exige 'apply' y CONFIRM_STAGING_APPLY=TA-039-STAGING." >&2
  exit 1
fi

terraform -chdir="${infra_dir}" apply staging.tfplan
echo "Infraestructura aplicada. Carga secretos antes del primer despliegue."
