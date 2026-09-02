#!/bin/zsh

set -euo pipefail

: "${MODEL_PATH:?Set MODEL_PATH to the downloaded Optimized-Speed-FP16 model directory}"

MTPLX_BIN="${MTPLX_BIN:-mtplx}"
MTPLX_HOST="${MTPLX_HOST:-127.0.0.1}"
MTPLX_PORT="${MTPLX_PORT:-18038}"
MODEL_ID="${MODEL_ID:-qwen3.8-27b-mtplx}"

print -r -- "Powered by MTPLX by Youssof Altoukhi"
print -r -- "https://github.com/youssofal/MTPLX"

exec "$MTPLX_BIN" quickstart \
  --model "$MODEL_PATH" \
  --model-id "$MODEL_ID" \
  --profile turbo \
  --host "$MTPLX_HOST" \
  --port "$MTPLX_PORT" \
  --mtp \
  --depth 3 \
  --reasoning off \
  --preserve-thinking off \
  --default-temperature 1.0 \
  --default-top-p 0.95 \
  --default-top-k 20 \
  --max-tokens 4096 \
  --scheduler-mode serial \
  --batching-preset solo \
  --ssd-session-cache off \
  --paged-kv-quantization off \
  --fan-mode default \
  --warmup-tokens 64 \
  --no-stats-footer
