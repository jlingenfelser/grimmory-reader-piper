# BookLore → Grimmory migration

Grimmory is descended from BookLore and existing users report successful in-place transitions by keeping the database and mounts while changing the application image. This repo takes the conservative version of that approach.

## Preserved

- `/srv/booklore-reader/mariadb`
- `/srv/booklore-reader/data`
- `/srv/booklore-reader/books`
- `/srv/booklore-reader/bookdrop`
- `/srv/booklore-reader/piper-data`
- Caddy certificate/config directories
- the old `/opt/booklore-reader` checkout

## Before migration

1. Confirm the GitHub Actions build succeeded.
2. Confirm both GHCR images are accessible from the Linode (public packages or `docker login ghcr.io`).
3. Run `scripts/migrate-from-booklore.sh`; it takes a DB/application-data backup before shutdown and pre-pulls all images while the old site is still online.

## Important rollback note

The first Grimmory boot may apply database migrations. Do not simply start the old BookLore application against a database that Grimmory has already migrated for long-term use. Restore the pre-migration SQL backup first if a true rollback is required.
