#!/bin/bash
# Regenerate sample_diff/feature.diff from scratch.
#
# Builds a tiny throwaway git repo (a "textstat" word-count tool), commits
# a v1, makes a realistic feature change (new function, a bug fix, docs,
# a new test file), stages it, and saves `git diff --staged` as the demo
# input. The sample diff is a REAL git artifact, produced by this script —
# never hand-written — so the demo parses exactly what git emits.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT
cd "$SCRATCH"
git init -q -b main
git config user.email "demo@example.com"
git config user.name "Demo"

mkdir -p textstat tests

cat > textstat/__init__.py <<'EOF'
"""textstat — tiny text statistics."""

__version__ = "0.1.0"
EOF

cat > textstat/count.py <<'EOF'
def count_words(text):
    return len(text.split())


def count_lines(text):
    return len(text.splitlines())
EOF

cat > README.md <<'EOF'
# textstat

Tiny text statistics: words and lines.
EOF

git add -A
git commit -qm "Initial commit"

# --- the change we will diff ---------------------------------------------

cat > textstat/count.py <<'EOF'
def count_words(text):
    return len(text.split())


def count_lines(text):
    if not text:
        return 0
    return len(text.splitlines())


def count_sentences(text):
    return sum(text.count(p) for p in ".!?")
EOF

cat > tests/test_count.py <<'EOF'
from textstat.count import count_lines, count_sentences


def test_count_lines_empty():
    assert count_lines("") == 0


def test_count_sentences():
    assert count_sentences("Hi. Bye! Really?") == 3
EOF

cat > README.md <<'EOF'
# textstat

Tiny text statistics: words, lines, and sentences.

## Usage

    from textstat.count import count_sentences
EOF

git add -A
git diff --staged > "$ROOT/sample_diff/feature.diff"
echo "Wrote sample_diff/feature.diff ($(wc -l < "$ROOT/sample_diff/feature.diff") lines)"
