#!/bin/sh
# Restore a backup produced by backup.sh into the production stack.
#
#   scripts/restore.sh <timestamp>        e.g. scripts/restore.sh 20261006T030000Z
#
# Checks the backup, stops the app services, restores the database and the document/artifact
# volumes, then starts everything again (also when the restore fails). The
# DOCUMENT_ENCRYPTION_KEY in use when the backup was taken is required to read the restored
# files. A backup taken before an upgrade can be restored: the app migrates it on start.
set -eu
TS="${1:?usage: restore.sh <timestamp>}"
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.production"
# Compose prefixes volume names with the project name (the directory name by default)
PROJECT="${COMPOSE_PROJECT_NAME:-$(basename "$PWD" | tr '[:upper:]' '[:lower:]')}"

# Both files must exist and be readable before anything is changed
if ! $COMPOSE run --rm --entrypoint sh backup -c "
  set -e
  test -f /backups/db-$TS.dump && test -f /backups/files-$TS.tar.gz
  pg_restore --list /backups/db-$TS.dump > /dev/null
  tar -tzf /backups/files-$TS.tar.gz > /dev/null
"; then
  echo "Backup $TS is missing or unreadable; nothing was changed" >&2
  exit 1
fi

$COMPOSE stop web backend worker beat
# Whatever happens from here, start the app again (after a failure, with the data as it was)
trap '$COMPOSE up -d' EXIT

# Into an empty schema, in one transaction: tables and columns added by migrations since the
# backup would otherwise block the restore, and a failure leaves the database untouched. The
# SQL is written out in full first, so a dump that turns out to be damaged changes nothing.
$COMPOSE run --rm --entrypoint sh backup -c "
  set -e
  pg_restore --no-owner --file=/tmp/restore.sql /backups/db-$TS.dump
  { echo 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'; cat /tmp/restore.sql; } > /tmp/full.sql
  psql --quiet -v ON_ERROR_STOP=1 --single-transaction --file=/tmp/full.sql > /dev/null
"

# Documents/artifacts are mounted read-only in the backup service; restore them via a throwaway container
docker run --rm \
  -v "${PROJECT}_backups:/backups:ro" \
  -v "${PROJECT}_documents_data:/data/documents" \
  -v "${PROJECT}_artifacts_data:/data/artifacts" \
  alpine sh -c "rm -rf /data/documents/* /data/artifacts/* && tar -xzf /backups/files-$TS.tar.gz -C /data"

echo "Restored backup $TS"
