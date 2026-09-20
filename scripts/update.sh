#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose pull booklore mariadb piper gateway
docker compose up -d --remove-orphans
docker image prune -f >/dev/null 2>&1 || true
docker compose ps
