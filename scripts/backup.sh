#!/usr/bin/env bash
# ==============================================================================
# Scheduled Automated Backup Script for CV Screening Platform
# Backs up PostgreSQL database and File Vault into timestamped archive
# ==============================================================================
set -euo pipefail

BACKUP_DIR="/srv/hermes-control/backups/cv-screening"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TARGET_DIR="${BACKUP_DIR}/${TIMESTAMP}"
mkdir -p "${TARGET_DIR}"

if [ -f "/srv/hermes-control/services/cv-screening/.env" ]; then
  set -a
  source "/srv/hermes-control/services/cv-screening/.env"
  set +a
fi

export LD_LIBRARY_PATH="/srv/apps/hermes/opt/postgresql/usr/lib/x86_64-linux-gnu"

echo "=== [1/3] Dumping PostgreSQL database 'cv_screening' ==="
/srv/apps/hermes/opt/postgresql/usr/lib/postgresql/16/bin/pg_dump \
  "${DATABASE_URL:-postgresql://cv_screening_user@127.0.0.1:5432/cv_screening}" \
  --format=custom --file="${TARGET_DIR}/cv_screening_${TIMESTAMP}.dump"

echo "=== [2/3] Archiving File Vault ==="
VAULT_DIR="/srv/hermes-control/services/cv-screening/data/cv-vault"
if [ -d "${VAULT_DIR}" ]; then
  tar -czf "${TARGET_DIR}/vault_${TIMESTAMP}.tar.gz" -C "/srv/hermes-control/services/cv-screening/data" cv-vault
else
  echo "Vault directory empty or not found, skipping."
fi

echo "=== [3/3] Generating SHA256 checksums ==="
cd "${TARGET_DIR}"
sha256sum * > SHA256SUMS.txt

echo "=== Backup completed successfully ==="
echo "Location: ${TARGET_DIR}"
ls -lh "${TARGET_DIR}"
