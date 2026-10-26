"""DiffScribe — let a local model write the commit message.

Local-first CLI that reads a git diff and drafts a conventional-commit
message plus a changelog entry using a local open-weight model, with
deterministic validation and a labeled rule-based fallback when the
model's text can't be validated.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
