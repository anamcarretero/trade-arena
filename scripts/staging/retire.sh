#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
infra_dir="${repository_dir}/infra/staging"
mode="${1:-plan}"

terraform -chdir="${infra_dir}" plan -destroy -out=retire.tfplan
if [[ "${mode}" == "plan" ]]; then
  echo "Solo plan de retirada. Conserva/verifica backup y desactiva deletion protection antes de aplicar."
  exit 0
fi
if [[ "${mode}" != "apply" || "${CONFIRM_STAGING_RETIRE:-}" != "RETIRE-TA-STAGING" ]]; then
  echo "Error: retirada exige 'apply' y CONFIRM_STAGING_RETIRE=RETIRE-TA-STAGING." >&2
  exit 1
fi

terraform -chdir="${infra_dir}" apply retire.tfplan
echo "Infraestructura retirada. Revisa manualmente retención del backup cifrado y revoca tokens externos."
