#!/usr/bin/env bash
set -euo pipefail
OLD_DIR=${OLD_DIR:-/opt/booklore-reader}
cd "$(dirname "$0")/.."
docker compose down
cd "$OLD_DIR"
docker compose up -d --remove-orphans
echo "Old BookLore stack started. NOTE: if Grimmory applied DB migrations, restoring the pre-migration SQL backup is safer before using BookLore long-term."
