# Grimmory Reader + Piper TTS

A pinned Grimmory v3.4.1 deployment carrying forward the custom Piper read-aloud system built for the previous BookLore installation.

## TTS features

- Select EPUB text → **Read aloud**. The first selected character is the anchor; selection length does not limit speech.
- Sentence-aware chunks (default ~650 characters) with configurable queue-ahead generation.
- Reader follows each spoken chunk by CFI, keeping Grimmory's progress near the audio position.
- Automatic continuation across EPUB sections.
- Pause / Resume / Stop and generation state.
- Sentence-pause, chunk-size, queue-depth, speed and Local-mode settings.
- Server Piper: `en_US-libritts_r-medium`, speaker 0.
- Optional browser-local Piper/ONNX/WASM mode.
- Mobile **Read from here** → tap text to choose the exact starting position.
- Reads the old `bookloreReaderTtsSettings` localStorage key when present and migrates settings to `grimmoryReaderTtsSettings`.

## Build model

The Linode does **not** compile Grimmory. GitHub Actions:

1. checks out the Grimmory release pinned in `config/upstream.env`;
2. applies `customizations/apply-customizations.py`;
3. installs the browser-Piper assets;
4. type-checks the customized frontend;
5. builds and pushes Grimmory to GHCR;
6. builds and pushes the patched Piper image to GHCR.

Images:

```text
ghcr.io/YOUR_USER/YOUR_REPO:latest
ghcr.io/YOUR_USER/YOUR_REPO-piper:latest
```

New GHCR packages may be private. Either make **both** packages public after the first successful workflow run, or run `docker login ghcr.io` on the Linode using a GitHub token with `read:packages`.

## Push to GitHub

Unzip this archive, enter the `grimmory-reader-piper` directory, then push it to your chosen repository. Both `master` and `main` trigger the image build workflow.

Wait for **Actions → Build customized Grimmory + Piper** to finish successfully before touching the Linode.

## Migrate the current Linode

Clone this repository alongside the old install; do not overwrite `/opt/booklore-reader`:

```bash
git clone https://github.com/YOUR_USER/YOUR_REPO.git /opt/grimmory-reader
cd /opt/grimmory-reader
GITHUB_REPOSITORY=YOUR_USER/YOUR_REPO ./scripts/migrate-from-booklore.sh
```

The migration helper backs up the existing database, reuses `/srv/booklore-reader`, pre-pulls all new images before downtime, stops the old stack, and starts Grimmory.

See `docs/MIGRATION.md`.

## Later updates

Push your changes and wait for the GitHub Actions build to pass, then on the Linode:

```bash
cd /opt/grimmory-reader
./scripts/update.sh
```

That only pulls prebuilt images and recreates containers.

## Persistent state

Production continues to use:

```text
/srv/booklore-reader
```

The old BookLore checkout at `/opt/booklore-reader` should be kept until Grimmory has been verified for a while.

## Scope

This first Grimmory port carries over the Piper reader/TTS functionality. The old custom **Paste Text → EPUB** feature is intentionally not ported in this first migration because Grimmory's ingest/EPUB APIs have changed; port it separately after the reader migration is stable.

## Licensing

Grimmory is AGPL-3.0. The customized built image remains subject to Grimmory's license and notices. Piper, piper-tts-web and voice models have their own upstream licenses.
