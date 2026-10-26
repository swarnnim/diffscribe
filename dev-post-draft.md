# DiffScribe: The Commit Message Writes Itself (Locally)

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 4: Ghost in the Machine](https://dev.to/challenges/hacktoberfest-week4-2026-10-26)*

## The most lied-to text box in software

Every developer knows the moment. The work is done, the tests pass, and
then you face the emptiest, most judgmental input field in all of
software: the commit message box. So you type what we all type:

```
fix stuff
updates
final version (2)
```

Git keeps perfect records of *what* changed. The *why* and the *what it
means* live in commit messages and changelogs — the two texts written
last, fastest, and worst. `git log` archaeology is a running joke
precisely because the record we leave behind is so much worse than the
work it describes.

The fashionable fix is to paste your diff into a cloud AI and let it
write the message. That works, and it also means shipping your
unreleased code — every secret you forgot to gitignore, every internal
hostname — to someone else's server, per commit, forever.

I wanted the drafting help without the disclosure. So for this week's
challenge I built **DiffScribe**: a small command-line tool that reads a
git diff and drafts a conventional-commit message and a changelog entry,
running entirely on my own machine. The AI at its core is an open-weight
model small enough to run on a laptop CPU. The interesting part isn't
that it works — it's *how little of the output the model is trusted
with*.

## What DiffScribe does

Stage some changes, run one command:

```bash
python3 -m diffscribe draft
```

It parses the diff, builds a compact digest (files, exact +/- counts,
and a few "signal" lines like new function definitions), and asks a
local model — Qwen2.5-0.5B-Instruct (Apache 2.0), served by llama.cpp
(MIT) — for two small wordings: a commit subject, and a handful of
changelog bullets. Then deterministic code takes over again: it
validates both texts, generates the per-file stats body itself, and
assembles the final draft with labels showing exactly which words came
from the model and which came from rules.

The governing rule of the whole design: **the model words things; code
counts things.** A language model — especially a half-billion-parameter
one — will happily write "+47 −13" whether or not those numbers are
true. So it is never given the chance. Every number in DiffScribe's
output was counted by parsing the diff.

## The demo — read it like a skeptic

`./scripts/demo.sh` drafts for a real staged diff: a README usage
section, a new test file, and a new `count_sentences` function added to
a toy text-statistics project. Recorded verbatim:

```
COMMIT MESSAGE:
feat: add docstring for textstat/count.py

Files changed: 3 (+20 -1)
- README.md: +5 -1 (modified)
- tests/test_count.py: +9 -0 (added)
- textstat/count.py: +6 -0 (modified)

CHANGELOG ENTRY (Unreleased):
- Updated README for easy navigation
- Added new installation steps
- Updated tests with new code
- Improved textstat count functionality
```

Now the honest reading, because this output is good *and* imperfect in
instructive ways. The subject is well-formed, correctly typed, and
points at the right file — but the diff adds a *function*, not a
docstring. The bullets are reasonable paraphrases, except "Added new
installation steps": the README gained a *usage* section, not install
steps. Nothing here is malformed, and nothing is quite fabricated —
it's the confident near-miss of a very small model.

That is exactly the failure profile I designed for. DiffScribe cannot
make a 0.5B model wise. What it can do is bound the blast radius:
validate the *shape* (conventional-commit format, length caps, bullet
counts), validate the *grounding* (more on that below), generate every
*fact-shaped* part itself, and label whatever the model did write so a
human editor — you, before you commit — knows what they're reviewing. A
drafter, supervised. Not an oracle.

## How it works

1. **Parse.** The unified diff becomes structured per-file changes:
   path, kind (added/modified/deleted/renamed), binary flag, exact
   added/deleted counts, and up to three signal lines per file (added
   lines that open a definition — `def`, `class`, `export function`…).
   One subtlety the tests cover: a content line can *look* like a diff
   header (`---deleted text` inside a removed string), so parsing keys
   off the `diff --git` file boundaries, not vibes.
2. **Digest.** The parsed change is rendered to a text digest capped at
   1,400 characters. Per-file entries truncate before whole files are
   dropped, and the exact totals line always survives — the model sees
   a faithful summary even for a huge diff, while the stats in the
   final output still cover every file.
3. **Draft.** Two separate model calls (subject, then bullets), each
   with a one-shot format example, greedy decoding — temperature 0, so
   the demo above reproduces byte-for-byte.
4. **Validate, per text, independently.** The subject must match the
   conventional-commit shape, fit 100 characters, and — the check I'm
   proudest of — its scope must be *grounded*: if the subject claims
   `feat(auth):`, the string "auth" must appear in a changed file's
   path or signal lines. Bullets must be 1–6 lines, each ≤ 140
   characters. Either text can fail on its own and be replaced by a
   labeled rule-based draft (type inferred from the change shape, exact
   stats included) without discarding the other.
5. **Assemble.** Stats body from code, wordings from wherever they
   legitimately came from, everything labeled.

There is also a `--no-llm` mode that skips the model entirely and emits
the pure deterministic draft — vaguer, and never wrong about the facts.
The full recorded transcript of both modes is `demo-output.txt` in the
repo.

## The run where my model lied with a straight face

The grounding check exists because of a specific, embarrassing run
early in development. My first one-shot example — meant only to teach
the output *format* — used an auth-flavored sample: a digest about
`auth/login.py`, subject `fix(auth): reject expired tokens during
login`. I then fed DiffScribe the text-statistics diff, and the model
returned, confidently and in perfect conventional-commit format:

```
feat(auth): reject expired tokens during login
```

There is no auth code in that diff. There is no login. The model hadn't
read my diff at all; it had copied my example and changed one word.
Every format check passed. This is the tiny-model failure mode that
matters: not gibberish — gibberish is easy to catch — but fluent,
well-formed, entirely wrong.

Two fixes. The example is now deliberately bland and topically distant
(a README edit), because an example a model might parrot should be one
whose parroting is obvious. And the deterministic grounding check: a
scoped subject whose scope appears nowhere in the diff is rejected and
replaced by the fallback, no matter how pretty it is. There's a
regression test named after the incident
(`test_assemble_rejects_leaked_example_subject`). The subject in the
demo — slightly wrong about "docstring", but genuinely about *this*
diff — is what the model produces under those constraints.

A second, quieter reuse bug deserves a sentence: I copied last week's
download script for llama.cpp, and it kept failing with a polite
"Not Found" before a `bash -x` trace showed why — the asset name in the
URL had a doubled letter (`llama-bb11580…`), a latent typo that had
been sitting in the old script all along. Inherited code inherits bugs.
It also inherits the ability to *find* them, because the script was
mine to read. Hold that thought for the next section.

## Why open innovation matters

This is the third week I've built on the same openly licensed stack —
open weights, an MIT inference engine, a standard-library-only program —
and DiffScribe is the week the compounding became visible.

**Reuse is real when the licenses let it be.** The llama.cpp wrapper,
the greedy-decoding discipline, the labeled-fallback pattern, even the
download scripts came straight from my Week 2 and Week 3 entries.
Nothing had to be re-negotiated, re-purchased, or re-permissioned; the
licenses (Apache 2.0, MIT) were the whole conversation. And when part
of what I reused turned out to be buggy, openness was the debugging
tool: the script was a file on my disk, readable to the last character,
fixable in one line.

**Open weights change who gets to build.** DiffScribe's model is a
~490 MB file I downloaded once. No account, no API key, no per-commit
bill, no terms-of-service roulette about whether my use case is allowed
this month. A student on a metered connection in Ahmedabad and a staff
engineer at a Fortune 500 company get *the same artifact* — and,
because it's just a file, the same ability to inspect what it is and
pin exactly which version produced an output. My demo reproduces
byte-for-byte because the weights, the engine version, and the decoding
settings are all fixed and named in the repo. That reproducibility is
an open-artifact property; a hosted model that silently changes under
you cannot offer it.

**Openness is also a quality strategy.** The most important line in
this project is a test that encodes a failure. Small open models fail
in public, cheaply, on your own machine, where you can watch them do it
and engineer around it — validation, grounding, fallbacks. That loop
(watch it fail → bound the failure → write the test) is the actual
craft of building with AI right now, and open tooling makes the loop
tight enough to run in an afternoon.

On this week's theme — **Ghost in the Machine** — DiffScribe fits on the honouring-the-past side of the brief, and I want to be plain about the limits of that fit: this is not a ghost-story generator, and it is not an ofrenda builder. What it is, is a keeper of a project's past. Every commit is a trace of work already done, and when those traces are written as "fix stuff", that past is effectively lost — the story of why a change was made fades, just as surely as an unrecorded memory does. DiffScribe tries to keep that history legible, drafting the commit message and changelog entry that let a future reader reconstruct what happened and why, from the diff itself. And there is a literal ghost in this machine, too: a half-billion-parameter open-weight model that lives entirely on my laptop, offline, drafting words in the dark with no server and no internet — a small, local presence that remembers how to phrase the past, and forgets nothing it was never sent.

## Honest limitations

- **Validation checks shape and grounding, not truth.** The demo
  subject says "docstring" where the diff adds a function; a bullet
  says "installation steps" where the README adds usage docs. Plausible
  near-misses survive every check I have. Read the draft before you
  commit — the tool assumes a human editor, which is why its outputs
  are labeled by origin.
- **Scope grounding is a substring heuristic.** It catches wholesale
  example leakage (its actual job), not subtle irrelevance; a scope of
  `auth` would also match a path containing `author`.
- **Huge diffs are digested, not read.** Past the digest cap, later
  files are summarized by counts alone; the model's wording may skew
  toward the early files. The stats body remains exact and complete.
- **Fallback drafting is deliberately vague** (`chore: update code
  (3 files, +20 -1)`) — correct about every fact it states, useless as
  prose. It is a safety net, not a writer.
- **No partner or hosted technology is used** — by design, not
  omission. The project's entire premise is that this job can be done
  locally, offline, with openly licensed parts.

## Prize Categories

None entered — no partner technology is used, by design (see Honest limitations above). This submission is entered for the overall prize only.

## Try it

Repo: https://github.com/swarnnim/diffscribe

```bash
git clone https://github.com/swarnnim/diffscribe && cd diffscribe
./scripts/download-llamacpp.sh && ./scripts/download-model.sh
./scripts/demo.sh                       # recorded demo, both modes
python3 -m unittest discover -s tests   # 50 tests
git add -A && python3 -m diffscribe draft   # draft for your own change
```

Standard library only; the downloads are the single network touch, and
after that DiffScribe will happily draft commit messages on a plane, in
a tunnel, or wherever your `git log` has been embarrassing you.

---

*DiffScribe was built in the open, from open parts, for the most
open-source month of the year. Week 1 taught me to ship small, Week 2
to keep data local, Week 3 to build the guardrails first. Week 4's
lesson: trust the model with the wording, never with the facts — and
write the test for the day it confuses the two.*
