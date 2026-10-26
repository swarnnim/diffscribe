#!/bin/bash
# Recorded demo: draft a commit message + changelog entry from the
# sample diff. Output is saved to demo-output.txt EXACTLY as produced —
# do not edit the file afterwards.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="demo-output.txt"
: > "$OUT"
{
  echo "=== DiffScribe demo — $(date -u '+%Y-%m-%d %H:%M UTC') ==="
  echo "Model: Qwen2.5-0.5B-Instruct (Q4_K_M, open weights, Apache 2.0)"
  echo "Engine: llama.cpp (MIT). 100% local, greedy decoding."
  echo "Input: sample_diff/feature.diff (a real staged diff, made by"
  echo "scripts/make-sample-diff.sh from a scratch repo)"
  echo ""
  echo "--- run 1: full draft with the local model ---"
  python3 -m diffscribe draft --diff sample_diff/feature.diff
  echo ""
  echo "--- run 2: deterministic rule-based fallback (--no-llm) ---"
  python3 -m diffscribe draft --no-llm --diff sample_diff/feature.diff
} 2>&1 | tee "$OUT"
echo ""
echo "Demo saved to $OUT"
