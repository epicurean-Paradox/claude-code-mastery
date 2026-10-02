#!/usr/bin/env python3
"""Tests for red-first-check.py (LESSONS Lesson 28), against throwaway git repos.

Wrong behaviour these catch: a new test that passes on the merge base slipping through
unmarked; a justified "pins existing behaviour" test, or a test that is red on the base,
being rejected; a changed (not new) test being treated as new; and a run that cannot
decide reporting success.
"""

import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest

CHECK = pathlib.Path(__file__).resolve().parent / "red-first-check.py"

LIB_BUGGY = "def add(a, b):\n    return a - b  # the bug\n"
LIB_FIXED = "def add(a, b):\n    return a + b\n"
HEADER = textwrap.dedent(
    """\
    import pathlib, sys, unittest
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from lib import add
    """
)
EXISTING = textwrap.dedent(
    """\

    class TestAdd(unittest.TestCase):
        def test_zero(self):
            self.assertEqual(add(0, 0), 0)
    """
)


class Repo:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name).resolve()
        self.git("init", "-q")
        self.write("lib.py", LIB_BUGGY)
        self.write("tests/test_lib.py", HEADER + EXISTING)
        self.base = self.commit("base")

    def git(self, *args):
        env = dict(
            os.environ,
            GIT_AUTHOR_NAME="t",
            GIT_AUTHOR_EMAIL="t@example.invalid",
            GIT_COMMITTER_NAME="t",
            GIT_COMMITTER_EMAIL="t@example.invalid",
        )
        r = subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        return r.stdout.strip()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def check(self, base=None):
        r = subprocess.run(
            [sys.executable, str(CHECK), "--base", base or self.base],
            capture_output=True,
            text=True,
            cwd=self.root,
            timeout=300,
        )
        return r.returncode, r.stdout + r.stderr

    def close(self):
        self._tmp.cleanup()


def pr_with(*methods, fix=True):
    """A PR that (optionally) fixes the bug and appends `methods` to TestAdd."""
    r = Repo()
    if fix:
        r.write("lib.py", LIB_FIXED)
    body = "".join(textwrap.indent(textwrap.dedent(m), "    ") for m in methods)
    r.write("tests/test_lib.py", HEADER + EXISTING + body)
    r.commit("pr")
    return r


RED = """
def test_adds(self):
    self.assertEqual(add(2, 3), 5)
"""
GREEN_UNMARKED = """
def test_zero_again(self):
    self.assertEqual(add(1, 1) * 0, 0)
"""
GREEN_MARKED = """
def test_identity(self):
    # red-first: pins existing behaviour (adding zero) against a regression
    self.assertEqual(add(4, 0), 4)
"""
GREEN_MARKED_NO_REASON = """
def test_identity_bare(self):
    # red-first: pins
    self.assertEqual(add(4, 0), 4)
"""


class TestRedFirstCheck(unittest.TestCase):
    def repo(self, *methods, fix=True):
        r = pr_with(*methods, fix=fix)
        self.addCleanup(r.close)
        return r

    def test_a_new_test_red_on_the_base_passes(self):
        code, out = self.repo(RED).check()
        self.assertEqual(code, 0, out)
        self.assertIn("TestAdd.test_adds", out)

    def test_a_new_test_green_on_the_base_fails_the_check(self):
        code, out = self.repo(RED, GREEN_UNMARKED).check()
        self.assertEqual(code, 1, out)
        self.assertIn("tests/test_lib.py:RED-FIRST:TestAdd.test_zero_again", out)

    def test_a_marked_pin_with_a_reason_is_allowed(self):
        code, out = self.repo(RED, GREEN_MARKED).check()
        self.assertEqual(code, 0, out)
        self.assertIn("pins", out)

    def test_a_marker_without_a_reason_is_not_enough(self):
        code, out = self.repo(GREEN_MARKED_NO_REASON).check()
        self.assertEqual(code, 1, out)

    def test_no_new_tests_is_a_pass(self):
        r = Repo()
        self.addCleanup(r.close)
        r.write("lib.py", LIB_FIXED)
        r.commit("fix only")
        code, out = r.check()
        self.assertEqual(code, 0, out)
        self.assertIn("no new tests", out)

    def test_a_changed_existing_test_is_not_new(self):
        r = Repo()
        self.addCleanup(r.close)
        r.write(
            "tests/test_lib.py",
            (HEADER + EXISTING).replace("add(0, 0), 0", "add(0, 0) + 0, 0"),
        )
        r.commit("edit existing")
        code, out = r.check()
        self.assertEqual(code, 0, out)
        self.assertIn("no new tests", out)

    def test_a_new_test_file_counts_every_test_as_new(self):
        r = Repo()
        self.addCleanup(r.close)
        r.write(
            "tests/test_more.py",
            HEADER
            + "\nclass TestMore(unittest.TestCase):\n    def test_one(self):\n        self.assertEqual(add(0, 0), 0)\n",
        )
        r.commit("new file")
        code, out = r.check()
        self.assertEqual(code, 1, out)
        self.assertIn("tests/test_more.py:RED-FIRST:TestMore.test_one", out)

    def test_a_test_whose_module_cannot_load_on_the_base_counts_as_red(self):
        r = Repo()
        self.addCleanup(r.close)
        r.write("newmod.py", "VALUE = 1\n")
        r.write(
            "tests/test_new.py",
            "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nfrom newmod import VALUE\n\nclass TestNew(unittest.TestCase):\n    def test_value(self):\n        self.assertEqual(VALUE, 1)\n",
        )
        r.commit("new module")
        code, out = r.check()
        self.assertEqual(code, 0, out)
        self.assertIn("could not run on the base", out)

    def test_the_check_runs_the_named_test_only(self):
        # test_sum passes on the base (unmarked: a violation). A red near-namesake must not
        # be run with it and make it look red.
        green = """
def test_sum(self):
    self.assertEqual(add(0, 0), 0)
"""
        red_namesake = """
def test_sum_positive(self):
    self.assertEqual(add(2, 2), 4)
"""
        code, out = self.repo(green, red_namesake).check()
        self.assertEqual(code, 1, out)
        self.assertIn("tests/test_lib.py:RED-FIRST:TestAdd.test_sum ", out)

    def test_an_unknown_base_is_a_usage_error(self):
        code, out = self.repo(RED).check(base="0" * 40)
        self.assertEqual(code, 2)
        self.assertIn("is not a commit in this repository", out)

    def test_the_worktree_is_removed(self):
        r = self.repo(RED)
        code, out = r.check()
        self.assertEqual(code, 0, out)
        self.assertIn("red on base", out)  # a worktree was really created and used
        self.assertNotIn("red-first-", r.git("worktree", "list"))


if __name__ == "__main__":
    unittest.main()
