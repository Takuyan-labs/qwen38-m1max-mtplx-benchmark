#!/bin/sh

set -eu

MTPLX_BASE_URL=${MTPLX_BASE_URL:-http://127.0.0.1:18038}
MTPLX_BASE_URL=${MTPLX_BASE_URL%/}
MTPLX_MODEL_ID=${MTPLX_MODEL_ID:-qwen3.8-27b-mtplx}
MTPLX_CLAUDE_EFFORT=${MTPLX_CLAUDE_EFFORT:-low}
CLAUDE_BIN=${CLAUDE_BIN:-}

if [ -z "$CLAUDE_BIN" ]; then
  CLAUDE_BIN=$(command -v claude || true)
fi
if [ -z "$CLAUDE_BIN" ] && [ -x "$HOME/.local/bin/claude" ]; then
  CLAUDE_BIN="$HOME/.local/bin/claude"
fi
if [ -z "$CLAUDE_BIN" ]; then
  printf '%s\n' 'Claude Code CLI was not found. Install it from https://code.claude.com/docs/en/setup' >&2
  exit 127
fi

if ! curl --fail --silent --show-error --max-time 3 "$MTPLX_BASE_URL/health" >/dev/null; then
  printf '%s\n' "MTPLX is not responding at $MTPLX_BASE_URL." >&2
  printf '%s\n' 'In another terminal, start the benchmark server with MODEL_PATH set:' >&2
  printf '%s\n' '  export MODEL_PATH="/path/to/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16"' >&2
  printf '%s\n' '  ./scripts/start_server.sh' >&2
  exit 1
fi

CLAUDE_CONFIG_DIR=${CLAUDE_CONFIG_DIR:-"$HOME/.claude/mtplx-27b"}
mkdir -p "$CLAUDE_CONFIG_DIR"
SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
if [ ! -f "$CLAUDE_CONFIG_DIR/settings.json" ]; then
  cp "$SCRIPT_DIR/../configs/claude-code-mtplx-settings.json" "$CLAUDE_CONFIG_DIR/settings.json"
fi

# Keep the fast local profile small, but explicitly include this project's instructions.
set -- --effort "$MTPLX_CLAUDE_EFFORT" --add-dir "$PWD" "$@"
if [ "${MTPLX_CLAUDE_BARE:-1}" = "1" ]; then
  set -- --bare "$@"
fi

# Keep this CLI profile isolated and make sure no real Anthropic API key is sent.
exec env -u ANTHROPIC_API_KEY \
  ANTHROPIC_BASE_URL="$MTPLX_BASE_URL" \
  ANTHROPIC_AUTH_TOKEN="${MTPLX_AUTH_TOKEN:-mtplx-local}" \
  ANTHROPIC_MODEL="$MTPLX_MODEL_ID" \
  ANTHROPIC_DEFAULT_OPUS_MODEL="$MTPLX_MODEL_ID" \
  ANTHROPIC_DEFAULT_SONNET_MODEL="$MTPLX_MODEL_ID" \
  ANTHROPIC_DEFAULT_HAIKU_MODEL="$MTPLX_MODEL_ID" \
  CLAUDE_CODE_SUBAGENT_MODEL="$MTPLX_MODEL_ID" \
  API_TIMEOUT_MS="${API_TIMEOUT_MS:-3000000}" \
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
  CLAUDE_CONFIG_DIR="$CLAUDE_CONFIG_DIR" \
  "$CLAUDE_BIN" "$@"
