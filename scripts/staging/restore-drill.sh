#!/usr/bin/env bash
set -euo pipefail

dump_file="${1:?Uso: restore-drill.sh BACKUP.dump --confirm-isolated}"
confirmation="${2:-}"
: "${RESTORE_DATABASE_URL:?Define RESTORE_DATABASE_URL de una base aislada y desechable}"

if [[ "${confirmation}" != "--confirm-isolated" ]]; then
  echo "Error: la restauración exige --confirm-isolated." >&2
  exit 1
fi
if [[ -n "${DATABASE_URL:-}" && "${RESTORE_DATABASE_URL}" == "${DATABASE_URL}" ]]; then
  echo "Error: RESTORE_DATABASE_URL coincide con DATABASE_URL de staging." >&2
  exit 1
fi

pg_restore --dbname="${RESTORE_DATABASE_URL}" \
  --clean --if-exists --no-owner "${dump_file}"
DATABASE_URL="${RESTORE_DATABASE_URL}" python3 -m tradearena migrate
psql --dbname="${RESTORE_DATABASE_URL}" -v ON_ERROR_STOP=1 -c \
  "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1" >/dev/null
echo "Restauración ensayada y migraciones verificadas en la base aislada."
