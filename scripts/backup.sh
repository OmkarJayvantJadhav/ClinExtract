#!/bin/sh
# Periodic backup loop (runs in the `backup` service of docker-compose.prod.yml).
# Each run writes, to /backups:
#   db-<timestamp>.dump        PostgreSQL custom-format dump (restore with pg_restore)
#   files-<timestamp>.tar.gz   stored documents + OCR artifacts (already encrypted at rest)
# and, only after both were written, deletes backups older than BACKUP_RETENTION_DAYS.
# The database dump contains patient data: copy backups to encrypted, access-controlled storage.
set -eu

INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
# After a failed run (e.g. the database not up yet after a reboot), try again this much sooner
RETRY_SECONDS="${BACKUP_RETRY_SECONDS:-300}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
DATA_DIR="${BACKUP_DATA_DIR:-/data}"

# Every step must succeed. Callers test the result (`if run_backup`), and inside such a test
# the shell ignores `set -e`, so each step returns explicitly on failure.
run_backup() {
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  echo "[backup] starting $ts"
  pg_dump --format=custom --file="$BACKUP_DIR/db-$ts.dump.partial" || return 1
  mv "$BACKUP_DIR/db-$ts.dump.partial" "$BACKUP_DIR/db-$ts.dump" || return 1
  tar -czf "$BACKUP_DIR/files-$ts.tar.gz.partial" -C "$DATA_DIR" documents artifacts || return 1
  mv "$BACKUP_DIR/files-$ts.tar.gz.partial" "$BACKUP_DIR/files-$ts.tar.gz" || return 1
  # Pruned only after a complete backup, so failing runs never remove the last good ones
  find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'files-*.tar.gz' \) -mtime +"$RETENTION_DAYS" -print -delete || return 1
  echo "[backup] finished $ts"
}

backup_failed() {
  rm -f "$BACKUP_DIR"/*.partial
  echo "[backup] FAILED at $(date -u +%Y%m%dT%H%M%SZ)" >&2
}

if [ "${1:-}" = "--once" ]; then
  if run_backup; then
    exit 0
  fi
  backup_failed
  exit 1
fi

while true; do
  if run_backup; then
    sleep "$INTERVAL"
  else
    backup_failed
    sleep "$RETRY_SECONDS"
  fi
done
