#!/usr/bin/env bash
set -euo pipefail
OLD_DIR=${OLD_DIR:-/opt/booklore-reader}
NEW_DIR=$(cd "$(dirname "$0")/.." && pwd)
if [[ $EUID -ne 0 ]]; then echo "Run as root." >&2; exit 1; fi
if [[ ! -f "$OLD_DIR/.env" ]]; then echo "Missing $OLD_DIR/.env" >&2; exit 1; fi
if [[ -z "${GITHUB_REPOSITORY:-}" ]]; then echo "Set GITHUB_REPOSITORY=owner/repo when running this script." >&2; exit 1; fi

cd "$NEW_DIR"
./scripts/backup-current.sh
cp "$OLD_DIR/.env" .env
sed -i '/^GRIMMORY_IMAGE=/d;/^PIPER_IMAGE=/d' .env
echo "GRIMMORY_IMAGE=ghcr.io/${GITHUB_REPOSITORY,,}:latest" >> .env
echo "PIPER_IMAGE=ghcr.io/${GITHUB_REPOSITORY,,}-piper:latest" >> .env

source .env
STATE=${STATE_DIR:-/srv/booklore-reader}
mkdir -p "$STATE"/{books,bookdrop,data,backups,caddy-data,caddy-config,piper-data}
chown -R "${APP_USER_ID:-1000}:${APP_GROUP_ID:-1000}" "$STATE/books" "$STATE/bookdrop" "$STATE/data" || true

# Important: prove all images are accessible before taking the old site down.
echo "Pre-pulling all new images while BookLore remains online..."
docker compose pull booklore mariadb piper gateway

echo "Stopping old BookLore stack..."
(cd "$OLD_DIR" && docker compose down)

echo "Starting Grimmory on the existing database and persistent volumes..."
docker compose up -d --remove-orphans

echo
echo "Migration started. Grimmory may run database migrations on first boot."
echo "Watch it with:"
echo "  cd $NEW_DIR && docker compose logs -f booklore"
echo "Then verify:"
echo "  docker compose ps"
