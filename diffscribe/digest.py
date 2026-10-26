"""Diff parsing: turn a unified diff into structured per-file stats and
a compact digest a tiny local model can reason over — plus the
deterministic rule-based drafting used when the model's text can't be
validated.

Honesty rule: every number in DiffScribe's output comes from this
module's counting, never from the model. The model only words the
subject and the bullets, and even those are validated before use.
"""

import re

MAX_FILES = 30
MAX_DIGEST_CHARS = 1400
SIGNALS_PER_FILE = 3
MAX_FALLBACK_BULLETS = 6

# Added lines that look like new code structure (definitions, exports).
_SIGNAL_RE = re.compile(
    r"^\s*(?:async\s+def|def|class|function|func|fn|export|public|private|"
    r"protected|static)\b.*"
)

_DOC_EXTS = (".md", ".rst", ".txt", ".adoc")


class FileChange:
    """One file's changes inside a unified diff."""

    def __init__(self, path):
        self.path = path
        self.added = 0
        self.deleted = 0
        self.kind = "modified"  # modified | added | deleted | renamed
        self.binary = False
        self.signals = []

    def totals_line(self):
        return f"+{self.added} -{self.deleted}"


def _b_path(diff_git_line):
    """Extract the b/ path from a 'diff --git a/X b/Y' line."""
    m = re.search(r"\sb/(.+)$", diff_git_line)
    return m.group(1) if m else diff_git_line.strip()


def parse_diff(text):
    """Parse a unified diff into a list of FileChange.

    Counts added/deleted lines per file (diff headers excluded), tracks
    added/deleted/renamed/binary files, and collects up to
    SIGNALS_PER_FILE 'signal' lines per file (added lines that look like
    new definitions). Content lines that merely start with '++'/'--' are
    counted correctly: only the real '+++ '/'--- ' header lines are
    skipped.
    """
    files = []
    cur = None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            cur = FileChange(_b_path(line))
            files.append(cur)
            continue
        if cur is None:
            continue
        if line.startswith("new file mode"):
            cur.kind = "added"
        elif line.startswith("deleted file mode"):
            cur.kind = "deleted"
        elif line.startswith("rename to "):
            cur.kind = "renamed"
            cur.path = line[len("rename to "):].strip()
        elif line.startswith("Binary files") or line.startswith("GIT binary patch"):
            cur.binary = True
        elif line.startswith("+++ ") or line.startswith("--- "):
            continue  # file headers, not content
        elif line.startswith("+"):
            cur.added += 1
            content = line[1:]
            if len(cur.signals) < SIGNALS_PER_FILE and _SIGNAL_RE.match(content):
                cur.signals.append(content.strip())
        elif line.startswith("-"):
            cur.deleted += 1
    return files[:MAX_FILES]


def totals(files):
    """Return (n_files, total_added, total_deleted)."""
    return (len(files),
            sum(f.added for f in files),
            sum(f.deleted for f in files))


def build_digest(files):
    """Build the compact text digest handed to the model.

    Per file: path, kind, +/- counts, and any signal lines. Truncated to
    MAX_DIGEST_CHARS (whole file entries are dropped from the end, with
    a marker) so a small context window can hold it. The TOTALS line is
    always present and always exact.
    """
    n, added, deleted = totals(files)
    total_line = f"TOTALS: {n} file{'s' if n != 1 else ''}, +{added} -{deleted}"
    header = "FILES CHANGED:"
    entries = []
    for f in files:
        entry = f"- {f.path} ({f.kind}): {f.totals_line()}"
        if f.binary:
            entry += "; binary file"
        if f.signals:
            entry += "; new code: " + "; ".join(f.signals)
        if len(entry) > 300:
            entry = entry[:297] + "…"
        entries.append(entry)
    kept = []
    used = len(header) + len(total_line) + 2
    for i, entry in enumerate(entries):
        if used + len(entry) + 1 > MAX_DIGEST_CHARS and kept:
            kept.append(f"- … and {len(entries) - i} more file(s)")
            break
        kept.append(entry)
        used += len(entry) + 1
    return "\n".join([header] + kept + [total_line])


# --- deterministic rule-based fallback drafting ------------------------------

def _is_doc(path):
    return path.lower().endswith(_DOC_EXTS)


def _is_test(path):
    base = path.rsplit("/", 1)[-1].lower()
    return ("test" in base or "/tests/" in "/" + path.lower()
            or path.lower().startswith("tests/"))


def infer_type(files):
    """Infer a conventional-commit type from file paths alone."""
    if files and all(_is_doc(f.path) for f in files):
        return "docs"
    if files and all(_is_test(f.path) for f in files):
        return "test"
    if any(f.kind == "added" and not _is_doc(f.path) and not _is_test(f.path)
           for f in files):
        return "feat"
    return "chore"


def infer_scope(files):
    """Common top-level directory shared by every file, or None."""
    tops = set()
    for f in files:
        parts = f.path.split("/")
        tops.add(parts[0] if len(parts) > 1 else None)
    if len(tops) == 1:
        top = tops.pop()
        if top and re.match(r"^[a-z0-9][a-z0-9_/.-]*$", top.lower()):
            return top.lower()
    return None


_TYPE_SUMMARIES = {
    "docs": "update documentation",
    "test": "update tests",
    "feat": "add new code",
    "chore": "update code",
    "fix": "fix code",
    "refactor": "refactor code",
}


def fallback_subject(files):
    """Deterministic conventional-commit subject from paths + counts."""
    n, added, deleted = totals(files)
    ctype = infer_type(files)
    scope = infer_scope(files)
    head = f"{ctype}({scope})" if scope else ctype
    summary = _TYPE_SUMMARIES.get(ctype, "update code")
    return f"{head}: {summary} ({n} file{'s' if n != 1 else ''}, +{added} -{deleted})"


def fallback_bullets(files):
    """Deterministic changelog bullets: one per file (capped)."""
    bullets = []
    for f in files[:MAX_FALLBACK_BULLETS]:
        bullets.append(f"- {f.path}: {f.totals_line()} ({f.kind})")
    if len(files) > MAX_FALLBACK_BULLETS:
        bullets.append(f"- … and {len(files) - MAX_FALLBACK_BULLETS} more file(s)")
    return bullets
