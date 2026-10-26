"""Command-line interface for DiffScribe."""

import argparse
import subprocess
import sys

from . import __version__
from .digest import build_digest, parse_diff
from .draft import assemble, render
from .llm import ask_bullets, ask_subject


def read_diff(args):
    """Get the unified diff text: from a file, stdin, or git staged."""
    if args.file:
        with open(args.file, "r", encoding="utf-8") as fh:
            return fh.read()
    if args.stdin:
        return sys.stdin.read()
    proc = subprocess.run(["git", "diff", "--staged"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "git diff --staged failed — run inside a git repository, or "
            "pass --diff FILE / --stdin.")
    if not proc.stdout.strip():
        raise RuntimeError(
            "no staged changes found — stage something with `git add`, "
            "or pass --diff FILE / --stdin.")
    return proc.stdout


def model_texts(digest, args):
    """Ask the model for (subject_reply, bullets_reply).

    Each call fails independently: a failure returns None for that text,
    and the assembler falls back (labeled) for just that piece.
    """
    kwargs = dict(model_path=args.model, cli_path=args.llamacpp,
                  threads=args.threads)
    subject_reply = bullets_reply = None
    try:
        subject_reply = ask_subject(digest, **kwargs)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"[model unavailable for the subject: {e}]", file=sys.stderr)
    try:
        bullets_reply = ask_bullets(digest, **kwargs)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"[model unavailable for the bullets: {e}]", file=sys.stderr)
    return subject_reply, bullets_reply


def cmd_draft(args):
    try:
        text = read_diff(args)
    except (OSError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    files = parse_diff(text)
    if not files:
        print("error: no file changes found in the diff.", file=sys.stderr)
        return 1
    digest = build_digest(files)

    if args.no_llm:
        draft = assemble(files)
        print(render(
            draft,
            method_note="rule-based fallback (--no-llm was passed; "
                        "no model was run)",
            label_fallbacks=False))
        return 0

    subject_reply, bullets_reply = model_texts(digest, args)
    draft = assemble(files, subject_reply, bullets_reply)
    fell_back = []
    if draft.subject_fallback:
        fell_back.append("subject")
    if draft.bullets_fallback:
        fell_back.append("bullets")
    if fell_back:
        method_note = (
            "local open-weight model Qwen2.5-0.5B-Instruct (Q4_K_M, "
            "Apache 2.0) via llama.cpp (greedy decoding); texts parsed "
            f"and validated — the {' and '.join(fell_back)} fell back to "
            "rule-based drafting and are marked above")
    else:
        method_note = (
            "local open-weight model Qwen2.5-0.5B-Instruct (Q4_K_M, "
            "Apache 2.0) via llama.cpp (greedy decoding); both texts "
            "parsed and validated, stats counted deterministically")
    print(render(draft, method_note=method_note))
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="diffscribe",
        description=("DiffScribe — let a local model write the commit "
                     "message. Drafts a conventional-commit message and "
                     "a changelog entry from a git diff, locally, with "
                     "an open-weight model."),
    )
    p.add_argument("--version", action="version",
                   version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("draft", help="draft a commit message + changelog "
                                     "entry from a diff")
    d.add_argument("--diff", dest="file", metavar="FILE",
                   help="read the unified diff from FILE "
                        "(default: `git diff --staged` in the current repo)")
    d.add_argument("--stdin", action="store_true",
                   help="read the unified diff from stdin")
    d.add_argument("--no-llm", action="store_true",
                   help="skip the model and use only the rule-based drafter")
    d.add_argument("--model", metavar="PATH",
                   help="GGUF model file (overrides DIFFSCRIBE_MODEL / "
                        "built-in default)")
    d.add_argument("--llamacpp", metavar="PATH",
                   help="llama-cli binary (overrides DIFFSCRIBE_LLAMACPP / "
                        "built-in default)")
    d.add_argument("--threads", type=int, default=2)
    d.set_defaults(func=cmd_draft)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
