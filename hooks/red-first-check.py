#!/usr/bin/env python3
"""red-first-check.py -- every NEW test must fail against the merge base (LESSONS Lesson 28).

    python3 red-first-check.py --base <merge-base-sha>

Finds the unittest test methods (`test*` in a class at module level, also under if/try/with,
in a `test_*.py` file) that exist at HEAD but not at the base. It parses both versions; a
renamed file is compared with its source, and a renamed method with an identical body is
not new. For each new test it:

  1. runs it alone against the BASE's code (a throwaway worktree with the PR's test files
     copied in): it must fail or error there -- a test that passes on the old code cannot
     see the defect the change fixes;
  2. runs it alone at HEAD: it must pass -- a test that never passes proves nothing.

The escape: a test that legitimately passes on the base (a mutant-killer, an over-strictness
guard) carries a COMMENT on its `def` line or in its body,

    # red-first: pins <what wrong behaviour it catches>   (at least 10 characters of reason)

-- not a string, not a docstring. Every pin is printed, so a reviewer sees each one.

Verdicts on the base: red (an assertion failed), error (an exception: printed with its type
so a reviewer can confirm it is red for the right reason -- a missing fixture or an
attribute the PR adds is red for the wrong one), timed out (counts as red), skipped or
expected-failure (indeterminate: a violation unless pinned), not collected (the AST id did
not run -- a mixin, a parametrised or generated id: a violation, the check cannot see it).

Limits: a changed (not new) test is not re-checked; tests inherited by a new subclass and
methods generated at runtime are not seen; subTest granularity is the whole test; the
runner is unittest. Exit 0 clean, 1 a violation, 2 usage (unknown base, not a repo).
"""

import ast
import io
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize

TEST_FILE_RE = re.compile(r"(^|/)test_[^/]*\.py$")
# The marker as a comment token, with a reason of at least 10 characters on the same line.
PIN_RE = re.compile(r"^#[ \t]*red-first:[ \t]*pins[ \t]+(\S.{9,})$")
RUN_TIMEOUT = int(os.environ.get("RED_FIRST_TIMEOUT", "300"))
SUMMARY_RE = re.compile(r"^(OK|FAILED)( \((.*)\))?$", re.M)
NOTES = {
    "red": "red on base",
    "error": "error on base ({why}): confirm it is red for the right reason",
    "timeout": "timed out on base ({why}): counts as red",
    "green": "green on base",
    "skipped": "skipped on the base: indeterminate",
    "xfail": "expected failure on the base: indeterminate",
    "uncollected": "not collected under its id on the base",
}


def git(*args, cwd="."):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def _classes(body):
    """Classes unittest would collect: at module level, or under if/try/with blocks."""
    for node in body:
        if isinstance(node, ast.ClassDef):
            yield node
        elif isinstance(node, (ast.If, ast.Try, ast.With)):
            for block in ("body", "orelse", "finalbody"):
                yield from _classes(getattr(node, block, []))
            for handler in getattr(node, "handlers", []):
                yield from _classes(handler.body)


def test_methods(source):
    """{"Class.test_x": (body fingerprint, first line, last line)}; raises SyntaxError."""
    tree = ast.parse(source)
    found = {}
    for cls in _classes(tree.body):
        for item in cls.body:
            is_func = isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            if is_func and item.name.startswith("test"):
                fingerprint = ast.dump(ast.Module(body=item.body, type_ignores=[]))
                found[f"{cls.name}.{item.name}"] = (
                    fingerprint,
                    item.lineno,
                    item.end_lineno,
                )
    return found


def pins(source, first, last):
    """Reasons of `# red-first: pins` COMMENT tokens between lines first..last."""
    reasons = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT and first <= tok.start[0] <= last:
            m = PIN_RE.match(tok.string.strip())
            if m:
                reasons.append(m.group(1).strip())
    return reasons


def changed_test_files(base):
    """[(head path, base path or None)] for test files added, modified or renamed."""
    fields = git("diff", "-z", "--name-status", "-M", base, "HEAD").split("\0")
    out, i = [], 0
    while i < len(fields) and fields[i]:
        status = fields[i]
        if status[0] in "RC":
            src, dst = fields[i + 1], fields[i + 2]
            i += 3
            if TEST_FILE_RE.search(dst):
                out.append((dst, src))
        else:
            path = fields[i + 1]
            i += 2
            if status[0] in "AM" and TEST_FILE_RE.search(path):
                out.append((path, path if status[0] == "M" else None))
    return out


def new_tests(base, files):
    """([(path, test_id, pin reasons)], [renamed ids], [parse errors])."""
    tests, renamed, errors = [], [], []
    for head_path, base_path in files:
        source = pathlib.Path(head_path).read_text(encoding="utf-8", errors="replace")
        try:
            head = test_methods(source)
        except SyntaxError as exc:
            errors.append(
                f"{head_path}:RED-FIRST:does not parse at HEAD (line {exc.lineno})"
            )
            continue
        before = {}
        if base_path:
            try:
                before = test_methods(git("show", f"{base}:{base_path}"))
            except (subprocess.CalledProcessError, SyntaxError):
                before = {}  # fails closed: every test in the file is new
        gone = {fp: tid for tid, (fp, _, _) in before.items() if tid not in head}
        for tid, (fp, first, last) in head.items():
            if tid in before:
                continue
            if fp in gone:
                renamed.append(f"{head_path} {tid} (renamed from {gone[fp]})")
                continue
            tests.append((head_path, tid, pins(source, first, last)))
    return tests, renamed, errors


def run_one(cwd, path, test_id):
    """(verdict, detail), verdict in green/red/error/timeout/skipped/xfail/uncollected."""
    file = pathlib.Path(path)
    cmd = [
        sys.executable, "-m", "unittest", "discover", "-v",
        "-s", str(file.parent) or ".", "-p", file.name,
        "-k", f"*.{test_id}",  # fnmatch over the full id: exactly this test
    ]  # fmt: skip
    try:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=RUN_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        return "timeout", f"after {RUN_TIMEOUT}s"
    out = r.stdout + r.stderr
    errors = re.findall(r"^(\w+(?:Error|Exception|Exit|Interrupt)):", out, re.M)
    if "unittest.loader._FailedTest" in out:
        return (
            "error",
            f"module did not load: {errors[-1] if errors else 'import failed'}",
        )
    ran = re.findall(r"^Ran (\d+) tests? in ", out, re.M)
    method = test_id.split(".")[-1]
    collected = re.search(
        rf"^{re.escape(method)} \([\w.]*\.{re.escape(test_id)}\)", out, re.M
    )
    if not ran or int(ran[-1]) != 1 or not collected:
        return "uncollected", ""
    summary = SUMMARY_RE.findall(out)
    status, detail = (summary[-1][0], summary[-1][2]) if summary else ("", "")
    if status == "OK":
        if "skipped" in detail:
            return "skipped", ""
        if "expected failures" in detail:
            return "xfail", ""
        return "green", ""
    if "failures=" in detail:
        return "red", ""
    return "error", errors[-1] if errors else "an exception"


def judge(path, test_id, reasons, on_base, why, at_head, head_why):
    """(summary line, [violations]) for one new test."""
    where = f"{path}:RED-FIRST:{test_id}"
    note = NOTES[on_base].format(why=why)
    pin = reasons[0] if reasons else ""
    violations = []
    if at_head != "green":
        violations.append(
            f"{where} does not pass at HEAD ({at_head}{': ' + head_why if head_why else ''})"
        )
    if "uncollected" in (on_base, at_head):
        violations.append(
            f"{where} not collected under its id (a mixin, a parametrised or "
            "generated id?): the check cannot see it run"
        )
    elif on_base in ("green", "skipped", "xfail") and not pin:
        violations.append(
            f"{where} is {note} -- it cannot see the defect. Make it fail on the old "
            "code, or add the comment '# red-first: pins <what wrong behaviour it catches>'"
        )
    line = f"  {path} {test_id}: {note}" + (f"; pinned: {pin}" if pin else "")
    return line, violations


def main(argv):
    if len(argv) != 3 or argv[1] != "--base":
        print("usage: red-first-check.py --base <sha>", file=sys.stderr)
        return 2
    base = argv[2]
    try:
        git("cat-file", "-e", f"{base}^{{commit}}")  # also fails outside a repository
    except subprocess.CalledProcessError:
        print(
            f"red-first-check: {base} is not a commit in this repository",
            file=sys.stderr,
        )
        return 2
    files = changed_test_files(base)
    tests, renamed, violations = new_tests(base, files)
    for line in renamed:
        print(f"  {line}: renamed, not new")
    if not tests:
        for line in violations:
            print(line)
        if not violations:
            print("red-first-check: no new tests in this change")
        return 1 if violations else 0

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="red-first-"))
    worktree = tmp / "base"
    summary = []
    try:
        git("worktree", "add", "--detach", "-q", str(worktree), base)
        for head_path, _ in files:  # the PR's tests, the base's code
            dest = worktree / head_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(head_path, dest)
        for path, test_id, reasons in tests:
            on_base, why = run_one(worktree, path, test_id)
            at_head, head_why = run_one(".", path, test_id)
            line, found = judge(path, test_id, reasons, on_base, why, at_head, head_why)
            print(line)
            summary.append(line)
            violations += found
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)], capture_output=True
        )
        shutil.rmtree(tmp, ignore_errors=True)
    for line in violations:
        print(line)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a") as fh:
            rows = "\n".join(f"- {s.strip()}" for s in summary + violations)
            fh.write(f"### red-first\n\n{rows}\n")
    print(
        f"red-first-check: {len(tests)} new test(s), {len(violations)} violation(s)",
        file=sys.stderr,
    )
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
