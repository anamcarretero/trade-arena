#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?Define DATABASE_URL de staging}"
destination="${1:-backups/tradearena-staging-$(date -u +%Y%m%d-%H%M%S).dump}"
mkdir -p "$(dirname "${destination}")"
umask 077
pg_dump --dbname="${DATABASE_URL}" \
  --format=custom --no-owner --file="${destination}"
pg_restore --list "${destination}" >/dev/null
echo "Backup verificable creado en ${destination}. Contiene datos sensibles; no lo subas a Git."
