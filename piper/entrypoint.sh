#!/usr/bin/env sh
set -eu
VOICE="${PIPER_VOICE:-en_US-libritts_r-medium}"
SENTENCE_SILENCE="${PIPER_SENTENCE_SILENCE:-0.40}"
if [ ! -f "/voices/${VOICE}.onnx" ] || [ ! -f "/voices/${VOICE}.onnx.json" ]; then
  python -m piper.download_voices --data-dir /voices "${VOICE}"
fi
exec python -m piper.http_server -m "${VOICE}" --data-dir /voices --host 0.0.0.0 --port 5000 --sentence-silence "${SENTENCE_SILENCE}"
