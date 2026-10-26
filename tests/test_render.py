"""Tests for rendering (diffscribe.draft.render + Draft.body_lines)."""

import unittest

from diffscribe.digest import FileChange
from diffscribe.draft import assemble, render


def fc(path, added=0, deleted=0, kind="modified"):
    f = FileChange(path)
    f.added, f.deleted, f.kind = added, deleted, kind
    return f


class TestRender(unittest.TestCase):

    def setUp(self):
        self.files = [fc("src/app.py", 10, 3), fc("README.md", 5, 1)]

    def test_body_lines_exact_stats(self):
        draft = assemble(self.files)
        body = draft.body_lines()
        self.assertEqual(body[0], "Files changed: 2 (+15 -4)")
        self.assertIn("- src/app.py: +10 -3 (modified)", body)
        self.assertIn("- README.md: +5 -1 (modified)", body)

    def test_render_sections(self):
        out = render(assemble(self.files), method_note="test method")
        self.assertIn("=== DIFFSCRIBE draft ===", out)
        self.assertIn("method: test method", out)
        self.assertIn("COMMIT MESSAGE:", out)
        self.assertIn("CHANGELOG ENTRY (Unreleased):", out)

    def test_render_labels_fallbacks(self):
        out = render(assemble(self.files), method_note="x")
        self.assertIn("subject drafted by the deterministic fallback", out)
        self.assertIn("bullets drafted by the deterministic fallback", out)

    def test_render_no_fallback_labels_when_model_used(self):
        draft = assemble(self.files,
                         subject_reply="feat(app): add the thing",
                         bullets_reply="- Added the thing")
        out = render(draft, method_note="x")
        self.assertNotIn("deterministic fallback", out)
        self.assertIn("feat(app): add the thing", out)

    def test_render_honesty_line(self):
        out = render(assemble(self.files), method_note="x")
        self.assertIn("Every number above was counted from the diff", out)

    def test_render_labels_can_be_suppressed(self):
        # --no-llm mode: the method note explains it; per-text labels
        # claiming a model text "could not be used" would mislead.
        out = render(assemble(self.files), method_note="x",
                     label_fallbacks=False)
        self.assertNotIn("drafted by the deterministic fallback", out)


if __name__ == "__main__":
    unittest.main()
