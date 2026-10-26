#!/bin/bash
# One-time download of the llama.cpp inference binary (MIT licensed).
# No compilation needed.
#
# The download goes through whatever proxy the machine sits behind; a
# flaky proxy can occasionally return an error page instead of the
# tarball. So: download to a temp file, VERIFY it is a real gzip, and
# retry the whole fetch a few times before giving up.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p llamacpp
if [ -x "llamacpp/llama-b11580/llama-cli" ]; then
  echo "llama-cli already present."
  exit 0
fi
VER="b11580"
URL="https://github.com/ggml-org/llama.cpp/releases/download/${VER}/llama-${VER}-bin-ubuntu-x64.tar.gz"
TMP="$(mktemp /tmp/llamacpp.XXXXXX.tgz)"
trap 'rm -f "$TMP"' EXIT
ok=""
for attempt in 1 2 3 4 5; do
  echo "Downloading llama.cpp ${VER} (ubuntu x64), attempt ${attempt}..."
  if curl -sfL --retry 2 -o "$TMP" "$URL" && tar tzf "$TMP" >/dev/null 2>&1; then
    ok=1
    break
  fi
  echo "  attempt ${attempt} did not yield a valid tarball; retrying..."
  sleep 3
done
if [ -z "$ok" ]; then
  echo "ERROR: could not download a valid llama.cpp tarball after 5 attempts." >&2
  exit 1
fi
tar xzf "$TMP" -C llamacpp --no-same-owner
chmod +x llamacpp/llama-b11580/llama-cli
./llamacpp/llama-b11580/llama-cli --version
echo "Installed under llamacpp/"
