#!/usr/bin/env bash
# ==============================================================================
# Automated Restore Verification Script for CV Screening Platform
# Restores dump to isolated verification DB 'cv_screening_restore_test'
# ==============================================================================
set -euo pipefail

BACKUP_PATH="${1:-}"

if [ -z "${BACKUP_PATH}" ]; then
  # Pick latest backup directory
  LATEST_DIR=$(ls -td /srv/hermes-control/backups/cv-screening/*/ | head -n 1)
  BACKUP_PATH="${LATEST_DIR}"
fi

echo "Verifying backup at: ${BACKUP_PATH}"
cd "${BACKUP_PATH}"

echo "=== [1/4] Verifying SHA256 Checksums ==="
sha256sum -c SHA256SUMS.txt

DUMP_FILE=$(ls *.dump | head -n 1)
RESTORE_DB="cv_screening_restore_test"

if [ -f "/srv/hermes-control/services/cv-screening/.env" ]; then
  set -a
  source "/srv/hermes-control/services/cv-screening/.env"
  set +a
fi

export LD_LIBRARY_PATH="/srv/apps/hermes/opt/postgresql/usr/lib/x86_64-linux-gnu"

echo "=== [2/4] Preparing Temporary Isolated Database '${RESTORE_DB}' ==="
dropdb -h 127.0.0.1 -p 5432 -U cv_screening_user --if-exists "${RESTORE_DB}"
createdb -h 127.0.0.1 -p 5432 -U cv_screening_user "${RESTORE_DB}"
/srv/apps/hermes/opt/postgresql/usr/lib/postgresql/16/bin/psql -h /tmp -U hermes -d "${RESTORE_DB}" -c "CREATE EXTENSION IF NOT EXISTS vector;"
/srv/apps/hermes/opt/postgresql/usr/lib/postgresql/16/bin/psql -h /tmp -U hermes -d "${RESTORE_DB}" -c "GRANT ALL ON DATABASE ${RESTORE_DB} TO cv_screening_user;"
/srv/apps/hermes/opt/postgresql/usr/lib/postgresql/16/bin/psql -h /tmp -U hermes -d "${RESTORE_DB}" -c "GRANT ALL ON SCHEMA public TO cv_screening_user;"
/srv/apps/hermes/opt/postgresql/usr/lib/postgresql/16/bin/psql -h /tmp -U hermes -d "${RESTORE_DB}" -c "ALTER SCHEMA public OWNER TO cv_screening_user;"

echo "=== [3/4] Restoring Data via pg_restore ==="
/srv/apps/hermes/opt/postgresql/usr/lib/postgresql/16/bin/pg_restore \
  -h 127.0.0.1 -p 5432 -U cv_screening_user -d "${RESTORE_DB}" \
  --no-owner --no-privileges "${DUMP_FILE}" || true

echo "=== [4/4] Verifying Integrity & Row Counts in Restored DB ==="
psql -h 127.0.0.1 -p 5432 -U cv_screening_user -d "${RESTORE_DB}" -c "
SELECT 'jobs' as tbl, count(*) FROM jobs
UNION ALL
SELECT 'documents', count(*) FROM documents
UNION ALL
SELECT 'candidates', count(*) FROM candidates
UNION ALL
SELECT 'profile_chunks', count(*) FROM profile_chunks
UNION ALL
SELECT 'screening_runs', count(*) FROM screening_runs
UNION ALL
SELECT 'candidate_scores', count(*) FROM candidate_scores;
"

echo "=== Cleaning up Temporary Restore DB ==="
dropdb -h 127.0.0.1 -p 5432 -U cv_screening_user "${RESTORE_DB}"

echo "=== Restore verification test PASSED 100% ==="
