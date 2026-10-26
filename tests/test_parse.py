"""Tests for diff parsing and digest building (diffscribe.digest)."""

import unittest

from diffscribe.digest import (
    MAX_DIGEST_CHARS, FileChange, build_digest, parse_diff, totals,
)

ONE_FILE = """\
diff --git a/src/app.py b/src/app.py
index 1111111..2222222 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,4 @@
 def main():
-    print("old")
+    print("new")
+    return 0
"""

NEW_AND_DELETED = """\
diff --git a/newmod.py b/newmod.py
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/newmod.py
@@ -0,0 +1,2 @@
+def hello():
+    pass
diff --git a/oldmod.py b/oldmod.py
deleted file mode 100644
index 4444444..0000000
--- a/oldmod.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def bye():
-    pass
"""

RENAME_AND_BINARY = """\
diff --git a/old/name.py b/new/name.py
similarity index 90%
rename from old/name.py
rename to new/name.py
diff --git a/logo.png b/logo.png
index 5555555..6666666 100644
Binary files a/logo.png and b/logo.png differ
"""

TRICKY_CONTENT = """\
diff --git a/notes.txt b/notes.txt
index 7777777..8888888 100644
--- a/notes.txt
+++ b/notes.txt
@@ -1,2 +1,2 @@
---foo is content, not a header
+++bar is content too
"""


class TestParseDiff(unittest.TestCase):

    def test_single_file_counts(self):
        files = parse_diff(ONE_FILE)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].path, "src/app.py")
        self.assertEqual(files[0].added, 2)
        self.assertEqual(files[0].deleted, 1)
        self.assertEqual(files[0].kind, "modified")
        self.assertFalse(files[0].binary)

    def test_headers_not_counted(self):
        # The --- / +++ header lines must not inflate the counts.
        files = parse_diff(ONE_FILE)
        self.assertEqual(totals(files), (1, 2, 1))

    def test_content_lines_that_look_like_headers(self):
        files = parse_diff(TRICKY_CONTENT)
        self.assertEqual(files[0].added, 1)    # +++bar content line
        self.assertEqual(files[0].deleted, 1)  # ---foo content line

    def test_new_and_deleted_kinds(self):
        files = parse_diff(NEW_AND_DELETED)
        self.assertEqual([f.kind for f in files], ["added", "deleted"])
        self.assertEqual(files[0].added, 2)
        self.assertEqual(files[1].deleted, 2)

    def test_rename_and_binary(self):
        files = parse_diff(RENAME_AND_BINARY)
        self.assertEqual(files[0].kind, "renamed")
        self.assertEqual(files[0].path, "new/name.py")
        self.assertTrue(files[1].binary)
        self.assertEqual(files[1].added, 0)

    def test_signal_extraction(self):
        files = parse_diff(NEW_AND_DELETED)
        self.assertIn("def hello():", files[0].signals)
        # plain added lines are not signals
        self.assertNotIn("pass", files[0].signals)

    def test_signals_capped(self):
        body = "".join(f"+def f{i}():\n" for i in range(6))
        diff = ("diff --git a/m.py b/m.py\nnew file mode 100644\n"
                "--- /dev/null\n+++ b/m.py\n@@ -0,0 +1,6 @@\n" + body)
        files = parse_diff(diff)
        self.assertEqual(len(files[0].signals), 3)

    def test_empty_diff(self):
        self.assertEqual(parse_diff(""), [])
        self.assertEqual(parse_diff("no diff here\n"), [])

    def test_preamble_ignored(self):
        files = parse_diff("random preamble\n+not a change\n" + ONE_FILE)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].added, 2)


class TestDigest(unittest.TestCase):

    def test_digest_contents(self):
        files = parse_diff(ONE_FILE + NEW_AND_DELETED)
        digest = build_digest(files)
        self.assertIn("src/app.py", digest)
        self.assertIn("TOTALS: 3 files, +4 -3", digest)
        self.assertIn("def hello():", digest)

    def test_digest_singular(self):
        files = parse_diff(ONE_FILE)
        self.assertIn("TOTALS: 1 file, +2 -1", build_digest(files))

    def test_digest_truncation_keeps_totals_exact(self):
        many = []
        for i in range(20):
            f = FileChange("some/really/long/path/component/file_%02d.py" % i)
            f.added, f.deleted = 10, 5
            f.signals = ["def some_function_with_a_long_name_%02d():" % i]
            many.append(f)
        digest = build_digest(many)
        self.assertLessEqual(len(digest), MAX_DIGEST_CHARS + 40)
        self.assertIn("more file(s)", digest)
        self.assertIn("TOTALS: 20 files, +200 -100", digest)


if __name__ == "__main__":
    unittest.main()
