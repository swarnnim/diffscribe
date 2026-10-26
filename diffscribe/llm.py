"""Thin wrapper around the llama.cpp `llama-cli` binary.

The open-weight model (Qwen2.5-0.5B-Instruct GGUF, Apache 2.0) and the
llama.cpp binary (MIT) both live on the user's machine. This module runs
one single-turn greedy generation per drafting job (commit subject, or
changelog bullets) and returns the model's raw text; the caller parses
and validates it.

DESIGN NOTE (carried over from the Week 3 build, discovered by testing):
a 0.5B model cannot hold one big structured document. It can hold one
small shape at a time — a single subject line, or a short list of
bullets. So DiffScribe asks for exactly those small shapes, one call
each, and every structural guarantee (conventional-commit format, line
counts, the stats body) is enforced by deterministic code in draft.py.
"""

import os
import shutil
import subprocess

SUBJECT_SYSTEM_PROMPT = (
    "You write git commit subjects. Reply with exactly one conventional "
    "commit subject line: a type word (feat, fix, docs, refactor, test, "
    "or chore), an optional short scope in parentheses, a colon, and a "
    "summary in the imperative mood, under 72 characters total. No "
    "period at the end. No other text."
)

BULLETS_SYSTEM_PROMPT = (
    "You write changelog bullets for end users. Reply with 2 to 4 short "
    "bullet lines, each starting with '- ', each describing one "
    "user-visible change in plain words. No heading, no other text."
)

SUBJECT_ANCHOR = "SUBJECT:"
BULLETS_ANCHOR = "BULLETS:"


def default_cli_path():
    """Locate the llama-cli binary: explicit env var, then the repo's
    llamacpp dir, then PATH."""
    env = os.environ.get("DIFFSCRIBE_LLAMACPP")
    if env and os.path.isfile(env):
        return env
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for cand in (
        os.path.join(here, "llamacpp", "llama-b11580", "llama-cli"),
        os.path.join(here, "llamacpp", "llama-cli"),
    ):
        if os.path.isfile(cand):
            return cand
    found = shutil.which("llama-cli")
    if found:
        return found
    raise FileNotFoundError(
        "llama-cli not found. Run scripts/download-llamacpp.sh, set "
        "DIFFSCRIBE_LLAMACPP, or put llama-cli on PATH."
    )


def default_model_path():
    env = os.environ.get("DIFFSCRIBE_MODEL")
    if env and os.path.isfile(env):
        return env
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local = os.path.join(here, "models", "qwen2.5-0.5b-instruct-q4_k_m.gguf")
    if os.path.isfile(local):
        return local
    raise FileNotFoundError(
        "Model not found. Run scripts/download-model.sh or set "
        "DIFFSCRIBE_MODEL."
    )


def extract_reply(cli_output, anchor):
    """Pull the generated text out of llama-cli's stdout.

    With --no-display-prompt the prompt is not echoed, so stdout is the
    reply followed by the '[ Prompt:' timings line. If an echo is
    present, the reply begins on the line after the ANCHOR line (or a
    truncation marker, or the last '> ' line).
    """
    lines = cli_output.splitlines()
    idx = None
    for i, line in enumerate(lines):
        if line.strip() == anchor:
            idx = i
    if idx is None:
        for i, line in enumerate(lines):
            if "(truncated)" in line:
                idx = i
    if idx is None:
        for i, line in enumerate(lines):
            if line.startswith("> "):
                idx = i
    if idx is None:
        idx = -1
    collected = []
    for line in lines[idx + 1:]:
        if line.startswith("[ Prompt:"):
            break
        collected.append(line)
    return "\n".join(collected).strip()


def generate(system_prompt, user_message, anchor, model_path=None,
             cli_path=None, max_tokens=80, threads=2, ctx_size=2048,
             temperature=0.0, timeout=300):
    """Run one single-turn greedy generation. Returns the reply text."""
    model_path = model_path or default_model_path()
    cli_path = cli_path or default_cli_path()
    cmd = [
        cli_path,
        "-m", model_path,
        "-sys", system_prompt,
        "--prompt", user_message,
        "-n", str(max_tokens),
        "-t", str(threads),
        "-c", str(ctx_size),
        "--temp", str(temperature),
        "--no-display-prompt",
        "-st",  # single turn, then exit (no interactive mode)
    ]
    env = dict(os.environ)
    cli_dir = os.path.dirname(cli_path)
    env["LD_LIBRARY_PATH"] = cli_dir + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, env=env)
    if proc.returncode != 0:
        raise RuntimeError(
            f"llama-cli failed (exit {proc.returncode}): {proc.stderr[-2000:]}"
        )
    reply = extract_reply(proc.stdout, anchor)
    if not reply:
        raise RuntimeError("llama-cli produced no reply text.")
    return reply


def build_subject_message(digest):
    # One-shot example: tiny models follow demonstrated shapes far better
    # than instructions alone. The example is deliberately bland and
    # topically distant (a README edit) — an earlier auth-flavored
    # example leaked straight into the output ("feat(auth): reject
    # expired tokens" for a diff that touched no auth code). The scope
    # grounding check in draft.py is the second line of defense.
    return (
        "EXAMPLE DIGEST:\n"
        "FILES CHANGED:\n"
        "- README.md (modified): +8 -2\n"
        "TOTALS: 1 file, +8 -2\n"
        "SUBJECT: docs: clarify install steps in the readme\n\n"
        "DIGEST:\n"
        f"{digest}\n"
        f"{SUBJECT_ANCHOR}"
    )


def build_bullets_message(digest):
    return (
        "EXAMPLE DIGEST:\n"
        "FILES CHANGED:\n"
        "- README.md (modified): +8 -2\n"
        "TOTALS: 1 file, +8 -2\n"
        "BULLETS:\n"
        "- Install steps in the README now match the current release\n\n"
        "DIGEST:\n"
        f"{digest}\n"
        f"{BULLETS_ANCHOR}"
    )


def ask_subject(digest, **kwargs):
    """Ask the model for one conventional-commit subject line."""
    return generate(SUBJECT_SYSTEM_PROMPT, build_subject_message(digest),
                    SUBJECT_ANCHOR, max_tokens=60, **kwargs)


def ask_bullets(digest, **kwargs):
    """Ask the model for 2-4 changelog bullets."""
    return generate(BULLETS_SYSTEM_PROMPT, build_bullets_message(digest),
                    BULLETS_ANCHOR, max_tokens=140, **kwargs)
