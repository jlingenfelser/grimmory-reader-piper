# Architecture

- Upstream is pinned to Grimmory v3.4.1.
- GitHub Actions checks out upstream, applies the TTS source overlay, type-checks it, and builds the customized Grimmory image.
- GitHub Actions also builds Piper 1.8.0 with the per-request sentence-silence / PCM-alignment patch.
- The Linode runs Caddy, Grimmory, MariaDB and Piper only; it performs no Angular, Gradle, or Piper image build.
- Caddy routes normal traffic to Grimmory and `/tts/*` to Piper.
- Persistent production state remains under `/srv/booklore-reader`, allowing migration from the current BookLore install without moving the database or books.
- The old `/opt/booklore-reader` checkout is deliberately retained during migration.
