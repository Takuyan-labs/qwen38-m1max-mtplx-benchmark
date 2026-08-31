#!/bin/zsh

set -euo pipefail

OUTPUT="${1:-results/raw/system-local.json}"
MTPLX_BIN="${MTPLX_BIN:-mtplx}"

product_version="$(sw_vers -productVersion)"
build_version="$(sw_vers -buildVersion)"
model_identifier="$(sysctl -n hw.model)"
memory_bytes="$(sysctl -n hw.memsize)"
chip="$(system_profiler SPHardwareDataType | awk -F': ' '/Chip:/ {print $2; exit}')"
gpu_cores="$(system_profiler SPDisplaysDataType | awk -F': ' '/Total Number of Cores:/ {print $2; exit}')"
metal_support="$(system_profiler SPDisplaysDataType | awk -F': ' '/Metal Support:/ {print $2; exit}')"
mtplx_version="$($MTPLX_BIN --version 2>/dev/null || true)"

mkdir -p "$(dirname "$OUTPUT")"

jq -n \
  --arg product_version "$product_version" \
  --arg build_version "$build_version" \
  --arg model_identifier "$model_identifier" \
  --arg chip "$chip" \
  --arg gpu_cores "$gpu_cores" \
  --arg metal_support "$metal_support" \
  --arg mtplx_version "$mtplx_version" \
  --argjson memory_bytes "$memory_bytes" '
  {
    macos: {version: $product_version, build: $build_version},
    hardware: {
      model_identifier: $model_identifier,
      chip: $chip,
      gpu_cores: ($gpu_cores | tonumber),
      memory_bytes: $memory_bytes,
      metal_support: $metal_support
    },
    runtime: {mtplx: $mtplx_version},
    privacy: "Serial number, hardware UUID, provisioning UDID, and user paths intentionally omitted"
  }' > "$OUTPUT"

echo "Saved $OUTPUT"
