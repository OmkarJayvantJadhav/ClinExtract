#!/bin/sh
# Restore a backup produced by backup.sh into the production stack.
#
#   scripts/restore.sh <timestamp>        e.g. scripts/restore.sh 20261006T030000Z
#
# Stops the app services, restores the database and the document/artifact volumes, then
# starts everything again. The DOCUMENT_ENCRYPTION_KEY in use when the backup was taken is
# required to read the restored files.
set -eu
TS="${1:?usage: restore.sh <timestamp>}"
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.production"
# Compose prefixes volume names with the project name (the directory name by default)
PROJECT="${COMPOSE_PROJECT_NAME:-$(basename "$PWD" | tr '[:upper:]' '[:lower:]')}"

$COMPOSE stop web backend worker beat

$COMPOSE run --rm --entrypoint sh backup -c "
  set -e
  test -f /backups/db-$TS.dump && test -f /backups/files-$TS.tar.gz
  pg_restore --clean --if-exists --no-owner --dbname=\"\$PGDATABASE\" /backups/db-$TS.dump
"

# Documents/artifacts are mounted read-only in the backup service; restore them via a throwaway container
docker run --rm \
  -v "${PROJECT}_backups:/backups:ro" \
  -v "${PROJECT}_documents_data:/data/documents" \
  -v "${PROJECT}_artifacts_data:/data/artifacts" \
  alpine sh -c "rm -rf /data/documents/* /data/artifacts/* && tar -xzf /backups/files-$TS.tar.gz -C /data"

$COMPOSE up -d
echo "Restored backup $TS"
