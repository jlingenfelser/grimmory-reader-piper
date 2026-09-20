#!/usr/bin/env bash
set -euo pipefail
OLD_DIR=${OLD_DIR:-/opt/booklore-reader}
STATE_DIR=${STATE_DIR:-/srv/booklore-reader}
mkdir -p "$STATE_DIR/backups"
ts=$(date +%Y%m%d-%H%M%S)
if [[ -x "$OLD_DIR/scripts/backup.sh" ]]; then
  (cd "$OLD_DIR" && ./scripts/backup.sh)
else
  echo "Old backup helper not found; attempting direct MariaDB dump"
  source "$OLD_DIR/.env"
  docker exec booklore-mariadb mariadb-dump -u"${DB_USER}" -p"${DB_PASSWORD}" "${DB_NAME}" > "$STATE_DIR/backups/pre-grimmory-$ts.sql"
fi
tar -C "$STATE_DIR" -czf "$STATE_DIR/backups/pre-grimmory-data-$ts.tgz" data 2>/dev/null || true
echo "Backup complete in $STATE_DIR/backups"
