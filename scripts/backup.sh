#!/bin/sh
# Periodic backup loop (runs in the `backup` service of docker-compose.prod.yml).
# Each run writes, to /backups:
#   db-<timestamp>.dump        PostgreSQL custom-format dump (restore with pg_restore)
#   files-<timestamp>.tar.gz   stored documents + OCR artifacts (already encrypted at rest)
# and deletes backups older than BACKUP_RETENTION_DAYS.
# The database dump contains patient data: copy backups to encrypted, access-controlled storage.
set -eu

INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

run_backup() {
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  echo "[backup] starting $ts"
  pg_dump --format=custom --file="/backups/db-$ts.dump.partial"
  mv "/backups/db-$ts.dump.partial" "/backups/db-$ts.dump"
  tar -czf "/backups/files-$ts.tar.gz.partial" -C /data documents artifacts
  mv "/backups/files-$ts.tar.gz.partial" "/backups/files-$ts.tar.gz"
  find /backups -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'files-*.tar.gz' \) -mtime +"$RETENTION_DAYS" -print -delete
  echo "[backup] finished $ts"
}

if [ "${1:-}" = "--once" ]; then
  run_backup
  exit 0
fi

while true; do
  if ! run_backup; then
    echo "[backup] FAILED at $(date -u +%Y%m%dT%H%M%SZ)" >&2
  fi
  sleep "$INTERVAL"
done
