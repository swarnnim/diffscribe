#!/bin/bash
# One-time download of the open-weight model used by SlothPlan.
# Qwen2.5-0.5B-Instruct, Q4_K_M GGUF (Apache 2.0) — ~397 MB, free, no account.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p models
URL="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
OUT="models/qwen2.5-0.5b-instruct-q4_k_m.gguf"
if [ -f "$OUT" ]; then
  echo "Model already present: $OUT"
  exit 0
fi
echo "Downloading Qwen2.5-0.5B-Instruct (Q4_K_M, ~397 MB)..."
curl -sL --retry 3 -o "$OUT" "$URL"
echo "Saved to $OUT"
