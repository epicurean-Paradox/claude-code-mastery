#!/usr/bin/env python3
"""red-first-check.py -- every NEW test must fail against the merge base (LESSONS Lesson 28).

    python3 red-first-check.py --base <merge-base-sha>

Finds the unittest test methods (`test*` in a class at module level; class and method also
under if/try/with, in a `test_*.py` file) that exist at HEAD but not at the base. It parses
both versions. A renamed file is compared with its source; a test that keeps its class,
decorators and body but changes name or file (a rename, a move) is not new -- one gone test
pairs with one new test, never with several. For each new test it:

  1. runs it at HEAD: it must pass -- a test that never passes proves nothing;
  2. runs it against the BASE's code (a throwaway worktree with the PR's test files copied
     in): it must fail or error there -- a test that passes on the old code cannot see the
     defect the change fixes.

Each run loads exactly that test (module path as discovery would import it, the class, the
method) in its own process and records the test's own outcome apart from class and module
fixtures. A method of a class that is not a TestCase runs through the TestCases in its module
that inherit it; with none, it is not a test. On the base, a name the test module imports
that the base does not define is stubbed (any use raises), so one new import does not turn
every test in the file red.

The escape: a test that legitimately passes on the base (a mutant-killer, an over-strictness
guard), or is skipped where the check runs, carries a COMMENT on its `def` line or in its body,

    # red-first: pins <what wrong behaviour it catches>   (at least 10 characters of reason)

-- not a string, not a docstring. Every pin is printed, so a reviewer sees each one.

Verdicts on the base: red (an assertion failed), error (an exception, a failing class or
module fixture, a missing name: printed so a reviewer can confirm it is red for the right
reason), timed out (counts as red), skipped or expected-failure (indeterminate: a violation
unless pinned), not collected (the class or method does not exist at run time: a violation).

Limits: a changed (not new) test is not re-checked; tests inherited by a new subclass and
methods generated at runtime are not seen; a test whose behaviour depends on its own name
can pass as a rename; subTest granularity is the whole test; a test module that imports a
whole module the PR adds cannot load on the base, so every test in it counts as red; changed
non-test files (fixture data) stay at the base's version; the runner is unittest. Exit 0
clean, 1 a violation, 2 usage (unknown base, not a repo).
"""

import ast
import collections
import io
import json
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
BLOCKS = (ast.If, ast.Try, ast.With) + (
    (ast.TryStar,) if hasattr(ast, "TryStar") else ()
)
# One verdict per TestCase that runs the test; the base keeps the most passing one, HEAD
# the least.
BASE_ORDER = (
    "not-a-test",
    "green",
    "skipped",
    "xfail",
    "uncollected",
    "timeout",
    "error",
    "red",
)
HEAD_ORDER = (
    "not-a-test",
    "uncollected",
    "timeout",
    "error",
    "red",
    "xfail",
    "skipped",
    "green",
)
NOTES = {
    "red": "red on base",
    "error": "error on base ({why}): confirm it is red for the right reason",
    "timeout": "timed out on base ({why}): counts as red",
    "green": "green on base",
    "skipped": "skipped on the base: indeterminate",
    "xfail": "expected failure on the base: indeterminate",
    "uncollected": "not collected under its id on the base",
    "not-a-test": "not run as a test on the base",
}

# Runs one test in a fresh interpreter: argv = test file, class, method, result file, mode.
DRIVER = r'''
import builtins, importlib, json, pathlib, sys, unittest

path, cls_name, method, out, mode = sys.argv[1:]


class MissingOnBase(Exception):
    pass


class Missing:
    """A name the test module imports that the base does not define: any use raises."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"<missing on base: {self.name}>"

    def _missing(self, *args, **kwargs):
        raise MissingOnBase(f"missing on base: {self.name}")

    __call__ = __getattr__ = __getitem__ = __iter__ = __len__ = __bool__ = _missing
    __eq__ = __lt__ = __le__ = __gt__ = __ge__ = __contains__ = _missing
    __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = _missing


def finish(*verdicts):
    with open(out, "w") as fh:
        json.dump(verdicts, fh)
    raise SystemExit(0)


file = pathlib.Path(path).resolve()
parts, top = [file.stem], file.parent
while (top / "__init__.py").exists():  # import it as discovery would: as package.module
    parts.insert(0, top.name)
    top = top.parent
module_name = ".".join(parts)
sys.path.insert(0, str(top))
real_import = builtins.__import__


def lenient_import(name, globals=None, locals=None, fromlist=(), level=0):
    module = real_import(name, globals, locals, fromlist, level)
    if mode == "base" and (globals or {}).get("__name__") == module_name:
        for attr in fromlist or ():
            if attr != "*" and not hasattr(module, attr):
                setattr(module, attr, Missing(f"{module.__name__}.{attr}"))
    return module


builtins.__import__ = lenient_import
try:
    module = importlib.import_module(module_name)
except BaseException as exc:
    finish(["error", f"module did not load: {type(exc).__name__}"])
finally:
    builtins.__import__ = real_import

cls = getattr(module, cls_name, None)
if not isinstance(cls, type):
    finish(["uncollected", ""])
if issubclass(cls, unittest.TestCase):
    runners = [cls]
else:
    runners = [
        c
        for c in vars(module).values()
        if isinstance(c, type) and issubclass(c, cls) and issubclass(c, unittest.TestCase)
    ]
    if not runners:
        finish(["not-a-test", ""])


class Record(unittest.TestResult):
    """Each test's own outcome, kept apart from class and module fixture errors."""

    def __init__(self):
        super().__init__()
        self.own, self.fixture, self.fixture_skipped = {}, [], False

    def why(self, err):
        return str(err[1]) if err[0] is MissingOnBase else err[0].__name__

    def addSuccess(self, test):
        self.own.setdefault(test, ["green", ""])

    def addFailure(self, test, err):
        self.own[test] = ["red", ""]

    def addError(self, test, err):
        if isinstance(test, unittest.TestCase):
            self.own[test] = ["error", self.why(err)]
        else:  # setUpClass, tearDownModule, ...
            self.fixture.append(f"{test.description}: {self.why(err)}")

    def addSkip(self, test, reason):
        if isinstance(test, unittest.TestCase):
            self.own[test] = ["skipped", ""]
        else:
            self.fixture_skipped = True

    def addExpectedFailure(self, test, err):
        self.own[test] = ["xfail", ""]

    def addUnexpectedSuccess(self, test):
        self.own[test] = ["red", "unexpected success"]

    def addSubTest(self, test, subtest, err):
        if err is not None:
            failed = issubclass(err[0], test.failureException)
            self.own[test] = ["red", ""] if failed else ["error", self.why(err)]


verdicts = []
for runner in runners:
    try:
        case = runner(method)
    except (AttributeError, ValueError):
        verdicts.append(["uncollected", ""])
        continue
    result = Record()
    unittest.TestSuite([case]).run(result)
    own = result.own.get(case)
    if result.fixture and (mode == "head" or own is None):
        verdicts.append(["error", result.fixture[0]])
    elif own:
        verdicts.append(own)
    else:
        verdicts.append(["skipped" if result.fixture_skipped else "uncollected", ""])
finish(*verdicts)
'''


def git(*args, cwd="."):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def _walk(body, kinds):
    """Nodes of `kinds` in a module or class body, also under if/try/with blocks."""
    for node in body:
        if isinstance(node, kinds):
            yield node
        elif isinstance(node, BLOCKS):
            for block in ("body", "orelse", "finalbody"):
                yield from _walk(getattr(node, block, []), kinds)
            for handler in getattr(node, "handlers", []):
                yield from _walk(handler.body, kinds)


def test_methods(source):
    """{"Class.test_x": (fingerprint, first line, last line)}; raises SyntaxError."""
    found = {}
    for cls in _walk(ast.parse(source).body, ast.ClassDef):
        for item in _walk(cls.body, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name.startswith("test"):
                nodes = [*item.decorator_list, *item.body]
                fingerprint = "|".join(ast.dump(n) for n in nodes)
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
    """[(head path or None, base path or None)] for test files the change touches."""
    fields = git("diff", "-z", "--name-status", "-M", base, "HEAD").split("\0")
    out, i = [], 0
    while i < len(fields) and fields[i]:
        status = fields[i][0]
        paths = fields[i + 1 : i + (3 if status in "RC" else 2)]
        i += 1 + len(paths)
        src, dst = paths[0], paths[-1]
        head = dst if status != "D" and TEST_FILE_RE.search(dst) else None
        before = src if status in "MTRD" and TEST_FILE_RE.search(src) else None
        if head or before:
            out.append((head, before))
    return out


def new_tests(base, files):
    """([(path, test_id, pin reasons)], [renamed ids], [parse errors])."""
    new, gone, errors = [], [], []
    for head_path, base_path in files:
        head, source = {}, ""
        if head_path:
            source = pathlib.Path(head_path).read_text(
                encoding="utf-8", errors="replace"
            )
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
            except (subprocess.CalledProcessError, SyntaxError, ValueError):
                before = {}  # fails closed: every test in the file is new
        for tid, (fp, first, last) in head.items():
            if tid not in before:
                new.append((head_path, tid, fp, pins(source, first, last)))
        gone += [
            (base_path, t, fp) for t, (fp, _, _) in before.items() if t not in head
        ]

    def key(test_id, fingerprint):
        return test_id.split(".")[0], fingerprint

    gone_keys = collections.Counter(key(t, fp) for _, t, fp in gone)
    new_keys = collections.Counter(key(t, fp) for _, t, fp, _ in new)
    origin = {key(t, fp): f"{p} {t}" for p, t, fp in gone}
    tests, renamed = [], []
    for path, tid, fp, reasons in new:
        k = key(tid, fp)
        if gone_keys[k] == 1 and new_keys[k] == 1:  # one to one, or it is not a rename
            renamed.append(f"{path} {tid} (renamed from {origin[k]})")
        else:
            tests.append((path, tid, reasons))
    return tests, renamed, errors


def run_one(cwd, path, test_id, mode, out, order):
    """(verdict, detail) of one test run alone; see DRIVER."""
    cls, method = test_id.split(".")
    cmd = [sys.executable, "-c", DRIVER, path, cls, method, str(out), mode]
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=RUN_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return "timeout", f"after {RUN_TIMEOUT}s"
    try:
        verdicts = json.loads(pathlib.Path(out).read_text())
    except (OSError, ValueError):
        tail = (r.stderr.strip().splitlines() or ["no output"])[-1][:200]
        return "error", f"no result: {tail}"
    verdict, detail = min(verdicts, key=lambda v: order.index(v[0]))
    return verdict, detail


def judge(path, test_id, reasons, on_base, why, at_head, head_why):
    """(summary line, [violations]) for one new test."""
    where = f"{path}:RED-FIRST:{test_id}"
    note = NOTES[on_base].format(why=why)
    pin = reasons[0] if reasons else ""
    violations = []
    if at_head == "uncollected" or on_base in ("uncollected", "not-a-test"):
        violations.append(
            f"{where} not collected under its id (a class defined only at run time, "
            "a generated id?): the check cannot see it run"
        )
    else:
        if at_head != "green" and not (at_head == "skipped" and pin):
            detail = f": {head_why}" if head_why else ""
            violations.append(f"{where} does not pass at HEAD ({at_head}{detail})")
        if on_base in ("green", "skipped", "xfail") and not pin:
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
            if head_path:
                dest = worktree / head_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.is_symlink():
                    dest.unlink()
                shutil.copyfile(head_path, dest)
        for n, (path, test_id, reasons) in enumerate(tests):
            at_head, head_why = run_one(
                ".", path, test_id, "head", tmp / f"{n}-head.json", HEAD_ORDER
            )
            if at_head == "not-a-test":
                line = f"  {path} {test_id}: not a test (no TestCase runs it)"
                print(line)
                summary.append(line)
                continue
            on_base, why = run_one(
                worktree, path, test_id, "base", tmp / f"{n}-base.json", BASE_ORDER
            )
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
