"""Tests for validation, fallback drafting, and assembly (draft.py +
the fallback half of digest.py)."""

import unittest

from diffscribe.digest import (
    FileChange, fallback_bullets, fallback_subject, infer_scope, infer_type,
)
from diffscribe.draft import (
    assemble, parse_bullets, parse_subject, subject_grounded,
)


def fc(path, added=0, deleted=0, kind="modified"):
    f = FileChange(path)
    f.added, f.deleted, f.kind = added, deleted, kind
    return f


class TestParseSubject(unittest.TestCase):

    def test_valid_plain(self):
        self.assertEqual(parse_subject("feat: add retry logic"),
                         "feat: add retry logic")

    def test_valid_scope(self):
        self.assertEqual(parse_subject("fix(auth): reject expired tokens"),
                         "fix(auth): reject expired tokens")

    def test_all_types_accepted(self):
        for t in ("feat", "fix", "docs", "style", "refactor", "perf",
                  "test", "build", "ci", "chore", "revert"):
            self.assertIsNotNone(parse_subject(f"{t}: do the thing"), t)

    def test_rejects_missing_type(self):
        self.assertIsNone(parse_subject("add retry logic"))

    def test_rejects_unknown_type(self):
        self.assertIsNone(parse_subject("banana: add retry logic"))

    def test_rejects_multiline(self):
        self.assertIsNone(parse_subject("feat: add x\nand a body line"))

    def test_rejects_trailing_period(self):
        self.assertIsNone(parse_subject("feat: add retry logic."))

    def test_rejects_too_long(self):
        self.assertIsNone(parse_subject("feat: " + "a" * 120))

    def test_accepts_exactly_max_length(self):
        line = "feat: " + "a" * 94  # exactly 100 chars
        self.assertEqual(parse_subject(line), line)

    def test_rejects_tiny_summary(self):
        self.assertIsNone(parse_subject("feat: ab"))

    def test_rejects_empty(self):
        self.assertIsNone(parse_subject(""))
        self.assertIsNone(parse_subject("   \n  "))


class TestParseBullets(unittest.TestCase):

    def test_valid_bullets(self):
        out = parse_bullets("- Added sentence counting\n- Fixed empty input")
        self.assertEqual(out, ["- Added sentence counting",
                               "- Fixed empty input"])

    def test_star_bullets_normalized(self):
        self.assertEqual(parse_bullets("* Added a thing"),
                         ["- Added a thing"])

    def test_none_without_bullets(self):
        self.assertIsNone(parse_bullets("Some prose with no bullets."))

    def test_rejects_too_many(self):
        reply = "\n".join(f"- bullet {i}" for i in range(7))
        self.assertIsNone(parse_bullets(reply))

    def test_rejects_overlong_bullet(self):
        self.assertIsNone(parse_bullets("- " + "x" * 141))


class TestFallbackDrafting(unittest.TestCase):

    def test_infer_type_docs(self):
        self.assertEqual(infer_type([fc("README.md", 5, 1)]), "docs")

    def test_infer_type_test(self):
        self.assertEqual(infer_type([fc("tests/test_a.py", 9, 0, "added")]),
                         "test")

    def test_infer_type_feat_for_new_code(self):
        self.assertEqual(infer_type([fc("src/new.py", 10, 0, "added")]),
                         "feat")

    def test_infer_type_chore_for_plain_modification(self):
        self.assertEqual(infer_type([fc("src/app.py", 2, 1)]), "chore")

    def test_infer_scope_shared_dir(self):
        files = [fc("src/a.py"), fc("src/b.py")]
        self.assertEqual(infer_scope(files), "src")

    def test_infer_scope_none_when_mixed(self):
        files = [fc("src/a.py"), fc("docs/b.md")]
        self.assertIsNone(infer_scope(files))

    def test_fallback_subject_counts_exact(self):
        files = [fc("src/a.py", 10, 3), fc("src/b.py", 0, 2)]
        self.assertEqual(fallback_subject(files),
                         "chore(src): update code (2 files, +10 -5)")

    def test_fallback_subject_docs(self):
        self.assertEqual(fallback_subject([fc("README.md", 5, 1)]),
                         "docs: update documentation (1 file, +5 -1)")

    def test_fallback_bullets_per_file_and_cap(self):
        files = [fc(f"f{i}.py", i, 0) for i in range(8)]
        bullets = fallback_bullets(files)
        self.assertEqual(len(bullets), 7)  # 6 files + the "more" line
        self.assertIn("more file(s)", bullets[-1])
        self.assertTrue(bullets[0].startswith("- f0.py: +0 -0 (modified)"))


class TestAssemble(unittest.TestCase):

    def setUp(self):
        self.files = [fc("src/app.py", 10, 3), fc("README.md", 5, 1)]

    def test_model_texts_used_when_valid(self):
        draft = assemble(self.files,
                         subject_reply="feat(app): add the thing",
                         bullets_reply="- Added the thing")
        self.assertEqual(draft.subject, "feat(app): add the thing")
        self.assertFalse(draft.subject_fallback)
        self.assertFalse(draft.bullets_fallback)

    def test_independent_fallback(self):
        draft = assemble(self.files,
                         subject_reply="no type here at all",
                         bullets_reply="- Added the thing")
        self.assertTrue(draft.subject_fallback)
        self.assertFalse(draft.bullets_fallback)
        self.assertEqual(draft.bullets, ["- Added the thing"])

    def test_both_fallback_without_replies(self):
        draft = assemble(self.files)
        self.assertTrue(draft.subject_fallback)
        self.assertTrue(draft.bullets_fallback)
        self.assertTrue(draft.subject.startswith("chore"))


class TestGrounding(unittest.TestCase):
    """The anti-leakage check: a well-formed subject whose scope appears
    nowhere in the diff is treated as unusable (the model parroted the
    one-shot example during development)."""

    def setUp(self):
        self.files = [fc("textstat/count.py", 6, 0),
                      fc("tests/test_count.py", 9, 0, "added")]

    def test_scopeless_subject_always_grounded(self):
        self.assertTrue(subject_grounded("feat: add sentence counting",
                                         self.files))

    def test_scope_matching_a_path_is_grounded(self):
        self.assertTrue(subject_grounded(
            "feat(textstat): add sentence counting", self.files))

    def test_foreign_scope_is_not_grounded(self):
        self.assertFalse(subject_grounded(
            "feat(auth): reject expired tokens during login", self.files))

    def test_assemble_rejects_leaked_example_subject(self):
        draft = assemble(
            self.files,
            subject_reply="feat(auth): reject expired tokens during login",
            bullets_reply="- Added sentence counting")
        self.assertTrue(draft.subject_fallback)
        self.assertFalse(draft.bullets_fallback)


if __name__ == "__main__":
    unittest.main()
