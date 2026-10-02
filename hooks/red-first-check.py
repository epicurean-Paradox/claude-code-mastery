#!/usr/bin/env python3
"""red-first-check.py -- every NEW test must fail against the merge base (LESSONS Lesson 28).

    python3 red-first-check.py --base <merge-base-sha>

Finds the test methods (`test*` in a class, in a `test_*.py` file) that exist at HEAD but
not at the base, by parsing both versions, not by string diff. It checks out the base in a
throwaway worktree, copies in the PR's test files only (the code under test stays at the
base), and runs each new test there on its own. A new test must fail or error there: a
test that passes against the old code cannot see the defect the change fixes.

Some new tests legitimately pass on the base: they pin behaviour that already works (a
mutant-killer, an over-strictness guard). Such a test carries a comment in its body,

    # red-first: pins <what wrong behaviour it would catch>

with a reason, the CI form of the Red-first gate's "state in one line what wrong behaviour
this test would catch". An unmarked new test that passes on the base fails the check.

Limits: a changed (not new) test is not re-checked; a test that cannot even load on the
base (it imports something the change adds) counts as red, and is reported so a reviewer
can confirm it is red for the right reason.

Output: one `path:RED-FIRST:Class.test ...` line per violation, plus a per-test summary.
Exit 0 all new tests red or pinned, 1 a violation, 2 usage (unknown base, not a repo).
"""

import ast
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

TEST_FILE_RE = re.compile(r"(^|/)test_[^/]*\.py$")
# The marker and its reason on one line: a bare marker followed by code is not a reason.
PIN_RE = re.compile(r"#[ \t]*red-first:[ \t]*pins[ \t]+\S")
RUN_TIMEOUT = 300


def git(*args, cwd="."):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def test_methods(source):
    """{"Class.test_x": function-source} for every test method of every top-level class."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    found = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(
                    item, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and item.name.startswith("test"):
                    found[f"{node.name}.{item.name}"] = (
                        ast.get_source_segment(source, item) or ""
                    )
    return found


def new_tests(base):
    """[(path, test_id, source)] for tests present at HEAD but not at `base`."""
    changed = git("diff", "--name-only", "--diff-filter=AM", base, "HEAD").split()
    result = []
    for path in sorted(p for p in changed if TEST_FILE_RE.search(p)):
        head = test_methods(
            pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
        )
        try:
            before = test_methods(git("show", f"{base}:{path}"))
        except subprocess.CalledProcessError:
            before = {}
        result += [(path, tid, src) for tid, src in head.items() if tid not in before]
    return result, [p for p in changed if TEST_FILE_RE.search(p)]


def run_on_base(worktree, path, test_id):
    """'red' | 'green' | 'unloadable' for one test, run alone against the base's code."""
    file = pathlib.Path(path)
    cmd = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(file.parent) or ".",
        "-p",
        file.name,
        "-k",
        f"*.{test_id}",  # fnmatch over the full id: exactly this test, no near-namesakes
    ]
    try:
        r = subprocess.run(
            cmd, cwd=worktree, capture_output=True, text=True, timeout=RUN_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        return "red"  # it did not pass
    out = r.stdout + r.stderr
    ran = re.search(r"^Ran (\d+) tests?", out, re.M)
    if not ran or int(ran.group(1)) == 0 or "unittest.loader._FailedTest" in out:
        return "unloadable"  # the module did not import on the base
    return "green" if r.returncode == 0 else "red"


def main(argv):
    if len(argv) != 3 or argv[1] != "--base":
        print("usage: red-first-check.py --base <sha>", file=sys.stderr)
        return 2
    base = argv[2]
    try:
        git("rev-parse", "--show-toplevel")
        git("cat-file", "-e", f"{base}^{{commit}}")
    except subprocess.CalledProcessError:
        print(
            f"red-first-check: {base} is not a commit in this repository",
            file=sys.stderr,
        )
        return 2
    tests, test_files = new_tests(base)
    if not tests:
        print("red-first-check: no new tests in this change")
        return 0

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="red-first-"))
    worktree = tmp / "base"
    violations = []
    try:
        git("worktree", "add", "--detach", "-q", str(worktree), base)
        for path in test_files:  # the PR's tests, the base's code
            dest = worktree / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
        for path, test_id, source in tests:
            verdict = run_on_base(worktree, path, test_id)
            pinned = bool(PIN_RE.search(source))
            if verdict == "green" and not pinned:
                violations.append(
                    f"{path}:RED-FIRST:{test_id} passes on the merge base: it cannot see the "
                    "defect. Make it fail on the old code, or mark it "
                    "'# red-first: pins <what wrong behaviour it catches>'"
                )
                note = "GREEN on base, unmarked"
            elif verdict == "green":
                note = "green on base, pins existing behaviour (marked)"
            elif verdict == "unloadable":
                note = "could not run on the base (counts as red; check it is red for the right reason)"
            else:
                note = "red on base"
            print(f"  {path} {test_id}: {note}")
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)], capture_output=True
        )
        shutil.rmtree(tmp, ignore_errors=True)
    for line in violations:
        print(line)
    print(
        f"red-first-check: {len(tests)} new test(s), {len(violations)} green on the base unmarked",
        file=sys.stderr,
    )
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
