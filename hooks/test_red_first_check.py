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

    def check(self, base=None, env=None, cwd=None):
        r = subprocess.run(
            [sys.executable, str(CHECK), "--base", base or self.base],
            capture_output=True,
            text=True,
            cwd=cwd or self.root,
            timeout=300,
            env=dict(os.environ, **(env or {})),
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
        self.assertIn("pinned: existing behaviour", out)

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
        r.write("lib.py", LIB_FIXED)
        r.write(
            "tests/test_more.py",
            HEADER
            + "\nclass TestMore(unittest.TestCase):\n"
            + "    def test_red(self):\n        self.assertEqual(add(2, 3), 5)\n\n"
            + "    def test_green(self):\n        self.assertEqual(add(0, 0), 0)\n",
        )
        r.commit("new file")
        code, out = r.check()
        self.assertEqual(code, 1, out)
        self.assertIn("tests/test_more.py:RED-FIRST:TestMore.test_green", out)
        self.assertNotIn("RED-FIRST:TestMore.test_red", out)

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
        self.assertIn("module did not load", out)

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
        self.assertNotIn("not collected", out)  # -k matched the namesake too

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


class TestReviewFindings(unittest.TestCase):
    """Escapes and false verdicts found in review, each seen red before its fix."""

    def repo(self):
        r = Repo()
        self.addCleanup(r.close)
        return r

    def test_a_renamed_test_file_with_a_new_green_test_is_caught(self):
        r = self.repo()
        r.git("mv", "tests/test_lib.py", "tests/test_lib_renamed.py")
        r.write("lib.py", LIB_FIXED)
        r.write(
            "tests/test_lib_renamed.py",
            HEADER
            + EXISTING
            + textwrap.indent(textwrap.dedent(GREEN_UNMARKED), "    "),
        )
        r.commit("rename")
        code, out = r.check()
        self.assertEqual(code, 1, out)
        self.assertIn("test_lib_renamed.py:RED-FIRST:TestAdd.test_zero_again", out)
        self.assertNotIn("RED-FIRST:TestAdd.test_zero ", out)  # existing test, not new

    def test_a_non_ascii_test_file_name_is_seen(self):
        r = self.repo()
        r.write(
            "tests/test_caf\u00e9.py",
            HEADER
            + "\nclass TestC(unittest.TestCase):\n    def test_g(self):\n        self.assertEqual(add(0, 0), 0)\n",
        )
        r.commit("non-ascii")
        code, out = r.check()
        self.assertEqual(code, 1, out)
        self.assertIn("RED-FIRST:TestC.test_g", out)

    def test_a_head_file_that_does_not_parse_fails_the_check(self):
        r = self.repo()
        r.write("tests/test_lib.py", HEADER + EXISTING + "    def test_broken(self:\n")
        r.commit("broken")
        code, out = r.check()
        self.assertEqual(code, 1, out)
        self.assertIn("does not parse", out)

    def test_a_class_under_an_if_is_scanned(self):
        r = self.repo()
        r.write(
            "tests/test_lib.py",
            HEADER
            + EXISTING
            + "\nif True:\n    class TestCond(unittest.TestCase):\n        def test_g(self):\n            self.assertEqual(add(0, 0), 0)\n",
        )
        r.commit("conditional class")
        code, out = r.check()
        self.assertEqual(code, 1, out)
        self.assertIn("RED-FIRST:TestCond.test_g", out)

    def test_a_test_not_collected_under_its_id_is_a_violation(self):
        r = self.repo()
        r.write("lib.py", LIB_FIXED)
        r.write(
            "tests/test_lib.py",
            HEADER
            + EXISTING
            + "\nclass Shapes:\n    def test_mixin(self):\n        self.assertEqual(add(0, 0), 0)\n\n\nclass TestMixed(Shapes, unittest.TestCase):\n    pass\n",
        )
        r.commit("mixin")
        code, out = r.check()
        self.assertEqual(code, 1, out)
        self.assertIn("not collected", out)

    def test_a_renamed_method_with_the_same_body_is_not_new(self):
        r = self.repo()
        r.write(
            "tests/test_lib.py",
            (HEADER + EXISTING).replace(
                "def test_zero(self)", "def test_zero_sum(self)"
            ),
        )
        r.commit("method rename")
        code, out = r.check()
        self.assertEqual(code, 0, out)
        self.assertIn("renamed", out)

    def test_a_test_skipped_on_the_base_is_not_red(self):
        r = self.repo()
        r.write("lib.py", LIB_FIXED + "SUPPORTED = True\n")
        r.write(
            "tests/test_lib.py",
            HEADER
            + "import lib\n"
            + EXISTING
            + "\n    @unittest.skipUnless(getattr(lib, 'SUPPORTED', False), 'needs SUPPORTED')\n    def test_supported(self):\n        self.assertEqual(add(1, 1), 2)\n",
        )
        r.commit("skip on base")
        code, out = r.check()
        self.assertEqual(code, 1, out)
        self.assertIn("skipped on the base", out)

    def test_a_marker_in_a_docstring_is_not_a_pin(self):
        r = self.repo()
        r.write(
            "tests/test_lib.py",
            HEADER
            + EXISTING
            + '\n    def test_doc(self):\n        """# red-first: pins a docstring is not a comment"""\n        self.assertEqual(add(0, 0), 0)\n',
        )
        r.commit("docstring marker")
        code, out = r.check()
        self.assertEqual(code, 1, out)

    def test_a_marker_reason_must_say_something(self):
        r = self.repo()
        r.write(
            "tests/test_lib.py",
            HEADER
            + EXISTING
            + "\n    def test_short(self):\n        # red-first: pins x\n        self.assertEqual(add(0, 0), 0)\n",
        )
        r.commit("short reason")
        code, out = r.check()
        self.assertEqual(code, 1, out)

    def test_a_marker_on_the_def_line_is_a_pin(self):
        r = self.repo()
        r.write(
            "tests/test_lib.py",
            HEADER
            + EXISTING
            + "\n    def test_pinned(self):  # red-first: pins adding zero against a regression\n        self.assertEqual(add(0, 0), 0)\n",
        )
        r.commit("def-line marker")
        code, out = r.check()
        self.assertEqual(code, 0, out)

    def test_a_new_test_must_also_pass_at_head(self):
        r = self.repo()
        r.write(
            "tests/test_lib.py",
            HEADER
            + EXISTING
            + "\n    def test_never(self):\n        self.assertEqual(1, 2)\n",
        )
        r.commit("never passes")
        code, out = r.check()
        self.assertEqual(code, 1, out)
        self.assertIn("does not pass at HEAD", out)

    def test_an_error_on_the_base_is_labelled(self):
        r = self.repo()
        r.write("lib.py", LIB_FIXED + "def mul(a, b):\n    return a * b\n")
        r.write(
            "tests/test_lib.py",
            HEADER
            + "import lib\n"
            + EXISTING
            + "\n    def test_mul(self):\n        self.assertEqual(lib.mul(2, 3), 6)\n",
        )
        r.commit("new function")
        code, out = r.check()
        self.assertEqual(code, 0, out)
        self.assertIn("error on base", out)
        self.assertIn("AttributeError", out)

    def test_a_timeout_on_the_base_counts_as_red(self):
        r = self.repo()
        r.write(
            "lib.py", "def add(a, b):\n    return a + b\n\ndef slow():\n    return 1\n"
        )
        r.git("add", "-A")
        r.git("commit", "-q", "-m", "x")
        base = r.git("rev-parse", "HEAD")
        r.write(
            "lib.py", "def add(a, b):\n    return a + b\n\ndef slow():\n    return 1\n"
        )
        r.write(
            "tests/test_slow.py",
            HEADER
            + "import lib, time\n\nclass TestSlow(unittest.TestCase):\n    def test_slow(self):\n        if not hasattr(lib, 'FAST'):\n            time.sleep(30)\n        self.assertEqual(lib.slow(), 1)\n",
        )
        r.write(
            "lib.py",
            "def add(a, b):\n    return a + b\n\ndef slow():\n    return 1\n\nFAST = True\n",
        )
        r.commit("slow on base")
        code, out = r.check(base=base, env={"RED_FIRST_TIMEOUT": "3"})
        self.assertEqual(code, 0, out)
        self.assertIn("timed out on base", out)

    def test_not_a_git_repository_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run(
                [sys.executable, str(CHECK), "--base", "0" * 40],
                capture_output=True,
                text=True,
                cwd=d,
            )
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("not a commit", r.stdout + r.stderr)

    def test_no_temporary_directory_is_left_behind(self):
        r = pr_with(RED)
        self.addCleanup(r.close)
        with tempfile.TemporaryDirectory() as tmp:
            code, out = r.check(env={"TMPDIR": tmp})
            self.assertEqual(code, 0, out)
            self.assertEqual(os.listdir(tmp), [])

    def test_an_async_test_is_seen(self):
        r = self.repo()
        r.write(
            "tests/test_lib.py",
            HEADER
            + EXISTING
            + "\nclass TestAsync(unittest.IsolatedAsyncioTestCase):\n    async def test_g(self):\n        self.assertEqual(add(0, 0), 0)\n",
        )
        r.commit("async test")
        code, out = r.check()
        self.assertEqual(code, 1, out)
        self.assertIn("RED-FIRST:TestAsync.test_g", out)

    def test_a_marker_in_an_f_string_is_not_a_pin(self):
        # Python 3.12+ tokenizes an f-string's text as its own token, starting with '#'.
        r = self.repo()
        r.write(
            "tests/test_lib.py",
            HEADER
            + EXISTING
            + '\n    def test_fstr(self):\n        f"# red-first: pins an f-string is not a comment"\n        self.assertEqual(add(0, 0), 0)\n',
        )
        r.commit("f-string marker")
        code, out = r.check()
        self.assertEqual(code, 1, out)


if __name__ == "__main__":
    unittest.main()
