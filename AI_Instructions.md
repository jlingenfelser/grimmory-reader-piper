# AI Instructions — Grimmory Reader + Piper

This repository is a source overlay for pinned Grimmory, not a fork that vendors the full upstream tree. `config/upstream.env` pins the supported upstream release. `customizations/apply-customizations.py` must fail loudly when its source anchors no longer match.

## Required TTS behavior

- Server Piper voice: `en_US-libritts_r-medium`, speaker 0 (LibriTTS speaker 3922).
- Selecting EPUB text anchors TTS at the first selected character; selection length does not limit playback.
- Queue sentence-aware chunks and continue through EPUB sections until paused/stopped/end-of-book.
- Move Grimmory to each chunk's CFI when that chunk begins playback so saved progress follows the spoken location.
- Mobile has `Read from here`; arming it makes the next tap on text a collapsed-range CFI and begins playback.
- Pause/Resume, Stop, and generation/loading state are visible while active.
- Reader settings persist under `grimmoryReaderTtsSettings`. Read legacy `bookloreReaderTtsSettings` so browsers retain old settings after migration.
- Browser-local mode uses `piper-tts-web`. CI must copy its `onnx`, `piper`, and `worker` runtime directories into `frontend/public` before the Docker build.
- Server Piper accepts per-request `sentence_silence`. Preserve the corrected 16-bit silence expression `bytes(int(sample_rate * sentence_silence) * 2)`.

## Deployment constraints

The production Linode has 2 GB RAM and must not compile Angular/Gradle there. GitHub Actions builds both images and publishes them to GHCR; production only pulls images and restarts containers.

Migration reuses `/srv/booklore-reader` and keeps `/opt/booklore-reader` for rollback reference. Always back up MariaDB before the first start of a new Grimmory version because database migrations may not be backwards-compatible.

## Updating Grimmory

Change `GRIMMORY_REF`, let CI apply the overlay, repair any `Upstream changed:` failures, and require frontend type-check plus Docker build success. Then test login/library browsing, reader progress, selection TTS, mobile tap-to-start, cross-section continuation, server Piper, browser-local Piper, and pause/resume/stop before production deployment.
