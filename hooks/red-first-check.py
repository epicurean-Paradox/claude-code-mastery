#!/usr/bin/env python3
"""red-first-check.py -- every NEW test must fail against the merge base (LESSONS Lesson 28).

    python3 red-first-check.py --base <merge-base-sha>

Finds the unittest test methods (`test*` in a class, nested classes and if/try/with blocks
included, in a `test_*.py` file) that exist at HEAD but not at the base. It parses both
versions; a renamed file is compared with its source, and a symlinked base file is read
through its link. A test that keeps its class, decorators, body and context (the class's
other members, the module-level names it uses) under a new name or in another file is a
rename, not new -- one gone test pairs with one new test, never with several. For each
new test it:

  1. runs it at HEAD: it must pass -- a test that never passes proves nothing;
  2. runs it against the BASE's code (a throwaway worktree with the PR's test files, the
     changed files under test-support directories and any missing `__init__.py` copied
     in): it must fail or error there -- a test that passes on the old code cannot see the
     defect the change fixes.

Each run loads exactly that test in its own interpreter, imports its module as discovery
would (package.module, else the file's own directory), and records the test's own outcome
apart from class and module fixtures. The test runs in every module-level TestCase that
inherits it, as discovery runs it, including subclasses in other test files; with none it
is not a test. On the base it counts as red if any of them is red. On the base, a name
the test module imports that HEAD resolves and the base lacks (outside a try/except
ImportError) is stubbed: the stub absorbs any use while the module is imported and raises
once tests run, and a test that names it directly counts as an error.

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
whole module the PR adds (`import newmod`) cannot load on the base, so every test in it
counts as red; changed files outside test-support directories stay at the base's version;
an editable install that points at the HEAD checkout imports HEAD's code on the base; a
test can always tell it runs in the base worktree; the runner is unittest. Exit 0 clean,
1 a violation, 2 usage (unknown base, not a repo).
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
# Changed files under these directories are test code or data, copied into the base.
SUPPORT_DIRS = set(
    os.environ.get(
        "RED_FIRST_SUPPORT_DIRS",
        "tests,test,testing,fixtures,testdata,test-fixtures,test_fixtures",
    ).split(",")
)
BLOCKS = (ast.If, ast.Try, ast.With) + (
    (ast.TryStar,) if hasattr(ast, "TryStar") else ()
)
BINDINGS = (
    ast.Import,
    ast.ImportFrom,
    ast.Assign,
    ast.AnnAssign,
    ast.AugAssign,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
)
# One verdict per TestCase that runs the test (skips dropped while another ran); the least
# passing wins, on the base and at HEAD.
ORDER = (
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

# Runs one test in a fresh interpreter. argv: test file, class qualname, method, mode
# (head/base), naming (package/flat), names to stub (JSON), other test files (JSON).
DRIVER = r'''
import ast, builtins, importlib, json, os, pathlib, sys, unittest, warnings

# The result file arrives in the environment and leaves it before any test code runs.
out = open(os.environ.pop("RED_FIRST_OUT"), "w")
path, qualname, method, mode, naming, stubs_json, others_json = sys.argv[1:]
del sys.argv[1:]
sys.path[0] = os.getcwd()  # absolute, as under `python -m unittest`: survives a chdir
ARMED = False
resolved, stubbed, load_errors = [], {}, []


def finish(*verdicts):
    json.dump({"verdicts": verdicts, "resolved": resolved}, out)
    out.close()
    os._exit(0)


class MissingOnBase(Exception):
    pass


class Missing:
    """A name only HEAD defines. While the test module is imported it absorbs every use
    (a constant derived from it, a decorator, a dict key); once tests run, any use raises."""

    def __init__(self, name):
        object.__setattr__(self, "_name", name)

    def __repr__(self):
        return f"<missing on base: {self._name}>"

    def _use(self, *args, **kwargs):
        if ARMED:
            raise MissingOnBase(f"missing on base: {self._name}")
        return self

    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return self._use()

    def __bool__(self):
        return self._use() is self

    def __hash__(self):
        self._use()
        return id(self)

    def __len__(self):
        self._use()
        return 0

    def __index__(self):
        self._use()
        return 0

    def __iter__(self):
        self._use()
        return iter(())

    __setattr__ = __call__ = __getitem__ = __setitem__ = __contains__ = _use
    __eq__ = __ne__ = __lt__ = __le__ = __gt__ = __ge__ = __neg__ = __pos__ = _use
    __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = _use
    __rtruediv__ = __floordiv__ = __mod__ = __pow__ = __or__ = __ror__ = __and__ = _use


class Proxy:
    """The module of one `from module import ...` statement, plus the stubbed names."""

    def __init__(self, module, stubs):
        self.__dict__.update(stubs)
        self.__dict__["_red_first_module"] = module

    def __getattr__(self, attr):
        return getattr(self.__dict__["_red_first_module"], attr)


root = pathlib.Path.cwd()


def locate(rel):
    """(top-level directory, module name) as discovery would import the file."""
    file = root / rel
    parts, top = [file.stem], file.parent
    while naming == "package" and top != root and (top / "__init__.py").exists():
        if not top.name.isidentifier():
            break
        parts.insert(0, top.name)
        top = top.parent
    return str(top), ".".join(parts)


def catches_import_error(handler):
    kinds = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    broad = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}
    return any(k is None or getattr(k, "id", getattr(k, "attr", "")) in broad for k in kinds)


tree = ast.parse((root / path).read_text(encoding="utf-8", errors="replace"))
froms, guarded = {}, set()
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        froms.update(dict.fromkeys(range(node.lineno, node.end_lineno + 1), node))
    elif isinstance(node, ast.Try) or type(node).__name__ == "TryStar":
        if any(catches_import_error(h) for h in node.handlers):
            for sub in (n for stmt in node.body for n in ast.walk(stmt)):
                if isinstance(sub, ast.ImportFrom):
                    guarded.update(range(sub.lineno, sub.end_lineno + 1))

top, module_name = locate(path)
sys.path.insert(0, top)
wanted = {tuple(pair) for pair in json.loads(stubs_json)}
real_import = builtins.__import__


def lenient_import(name, globals=None, locals=None, fromlist=(), level=0):
    module = real_import(name, globals, locals, fromlist, level)
    if not fromlist or (globals or {}).get("__name__") != module_name:
        return module
    line = sys._getframe(1).f_lineno
    stubs = {}
    for attr in fromlist:
        if attr == "*":
            continue
        if hasattr(module, attr):
            resolved.append([module.__name__, attr])
        elif (module.__name__, attr) in wanted and line not in guarded:  # base runs only
            stubs[attr] = Missing(f"{module.__name__}.{attr}")
            for alias in froms[line].names if line in froms else ():
                if alias.name == attr:
                    stubbed[alias.asname or attr] = f"{module.__name__}.{attr}"
    return Proxy(module, stubs) if stubs else module


builtins.__import__ = lenient_import
try:
    loaded = [importlib.import_module(module_name)]
except BaseException as exc:
    finish(["error", f"module did not load: {type(exc).__name__}"])
finally:
    builtins.__import__ = real_import
for other in json.loads(others_json):
    other_top, other_name = locate(other)
    if other_name == module_name:
        continue
    sys.path.insert(1, other_top)
    try:
        loaded.append(importlib.import_module(other_name))
    except BaseException as exc:
        load_errors.append(f"{other}: module did not load: {type(exc).__name__}")
ARMED = True


def method_node(body, parts):
    for node in body:
        if isinstance(node, (ast.If, ast.Try, ast.With)) or type(node).__name__ == "TryStar":
            blocks = [node.body, getattr(node, "orelse", []), getattr(node, "finalbody", [])]
            for block in blocks + [h.body for h in getattr(node, "handlers", [])]:
                found = method_node(block, parts)
                if found:
                    return found
        elif len(parts) > 1 and isinstance(node, ast.ClassDef) and node.name == parts[0]:
            found = method_node(node.body, parts[1:])
            if found:
                return found
        elif len(parts) == 1 and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == parts[0]:
                return node
    return None


if stubbed:  # a test that names a missing name cannot run on the real base
    node = method_node(tree.body, qualname.split(".") + [method])
    used = {n.id for s in (node.body if node else []) for n in ast.walk(s) if isinstance(n, ast.Name)}
    hit = sorted(stubbed[n] for n in used & stubbed.keys())
    if hit:
        finish(["error", "missing on base: " + ", ".join(hit)])

module = loaded[0]
classes = [c for m in loaded for c in vars(m).values() if isinstance(c, type)]
target = module
for part in qualname.split("."):
    target = getattr(target, part, None)
if not isinstance(target, type):  # a base class deleted after use (`del Base`)
    target = next(
        (b for c in classes for b in c.__mro__ if b.__qualname__ == qualname and b.__module__ == module_name),
        None,
    )
if target is None:
    finish(["uncollected", ""])


def same(b):
    tail = b.__module__.rsplit(".", 1)[-1] == target.__module__.rsplit(".", 1)[-1]
    return b is target or (b.__qualname__ == target.__qualname__ and tail)


runners = []
for c in classes:  # what discovery runs: module-level TestCases that inherit the method
    if issubclass(c, unittest.TestCase) and c not in runners and any(map(same, c.__mro__)):
        if callable(getattr(c, method, None)):
            runners.append(c)
if not runners:
    finish(*([["error", e] for e in load_errors] or [["not-a-test", ""]]))


class Record(unittest.TestResult):
    """Each test's own outcome, kept apart from class and module fixture errors."""

    def __init__(self):
        super().__init__()
        self.own, self.fixture, self.fixture_skipped = {}, [], False
        self.subpassed, self.subskipped = set(), set()

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
        if hasattr(test, "test_case"):  # a skipped subTest
            self.subskipped.add(test.test_case)
        elif isinstance(test, unittest.TestCase):
            self.own[test] = ["skipped", ""]
        else:
            self.fixture_skipped = True

    def addExpectedFailure(self, test, err):
        self.own[test] = ["xfail", ""]

    def addUnexpectedSuccess(self, test):
        self.own[test] = ["red", "unexpected success"]

    def addSubTest(self, test, subtest, err):
        if err is None:
            self.subpassed.add(test)
        else:
            failed = issubclass(err[0], test.failureException)
            self.own[test] = ["red", ""] if failed else ["error", self.why(err)]


verdicts = [["error", e] for e in load_errors]
for runner in runners:
    try:
        case = runner(method)
    except ValueError:
        verdicts.append(["uncollected", ""])
        continue
    except Exception as exc:
        verdicts.append(["error", f"{type(exc).__name__} building the test"])
        continue
    result = Record()
    with warnings.catch_warnings():
        if not sys.warnoptions:
            warnings.simplefilter("default")  # what unittest's runner installs
        unittest.TestSuite([case]).run(result)
    own = result.own.get(case)
    if own is None and case in result.subskipped:
        own = ["green", ""] if case in result.subpassed else ["skipped", ""]
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


def changes(base):
    """[(status letter, base path, head path)] for every file the change touches."""
    fields = git("diff", "-z", "--name-status", "-M", base, "HEAD").split("\0")
    out, i = [], 0
    while i < len(fields) and fields[i]:
        status = fields[i][0]
        paths = fields[i + 1 : i + (3 if status in "RC" else 2)]
        i += 1 + len(paths)
        out.append((status, paths[0], paths[-1]))
    return out


def changed_test_files(entries):
    """[(head path or None, base path or None)] for the test files among `entries`."""
    out = []
    for status, src, dst in entries:
        head = dst if status != "D" and TEST_FILE_RE.search(dst) else None
        before = src if status in "MTRD" and TEST_FILE_RE.search(src) else None
        if head or before:
            out.append((head, before))
    return out


def support_files(entries):
    """Changed files that are test code or data: under a test-support directory."""
    return [
        dst
        for status, _, dst in entries
        if status != "D"
        and not TEST_FILE_RE.search(dst)
        and (SUPPORT_DIRS & set(dst.split("/")[:-1]) or dst.endswith("conftest.py"))
    ]


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


def _test_classes(body, prefix=""):
    """(qualified name, class) for every class, nested ones included."""
    for cls in _walk(body, ast.ClassDef):
        yield prefix + cls.name, cls
        yield from _test_classes(cls.body, f"{prefix}{cls.name}.")


def _bound(stmt):
    """Names a module-level statement binds."""
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {stmt.name}
    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
        return {(a.asname or a.name).split(".")[0] for a in stmt.names}
    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
    return {n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)}


def _names(nodes):
    return {n.id for node in nodes for n in ast.walk(node) if isinstance(n, ast.Name)}


def _module_context(binders, names, own_class):
    """Dumps of the module-level statements that bind `names`, followed transitively."""
    seen, todo, dumps = {own_class}, set(names), set()
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        for stmt in binders.get(name, ()):
            dumps.add(ast.dump(stmt))
            todo |= _names([stmt])
    return "|".join(sorted(dumps))


def test_methods(source):
    """{"Class.test_x": (rename key, first line, last line)}; raises SyntaxError."""
    tree = ast.parse(source)
    binders = collections.defaultdict(list)
    for stmt in _walk(tree.body, BINDINGS):
        for name in _bound(stmt):
            binders[name].append(stmt)
    found = {}
    for qualname, cls in _test_classes(tree.body):
        members = [
            n
            for n in cls.body
            if not isinstance(n, ast.ClassDef)
            and not (
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name.startswith("test")
            )
        ]
        heading = [*cls.bases, *cls.keywords, *cls.decorator_list]
        class_context = "|".join(ast.dump(n) for n in [*heading, *members])
        for item in _walk(cls.body, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name.startswith("test"):
                own = "|".join(ast.dump(n) for n in [*item.decorator_list, *item.body])
                names = _names([item, *heading, *members])
                context = _module_context(binders, names, qualname.split(".")[0])
                found[f"{qualname}.{item.name}"] = (
                    "#".join((own, class_context, context)),
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


def base_source(base, path):
    """A file's text at the base, read through a symlink that stays in the repository."""
    if git("ls-tree", base, "--", path).split()[:1] == ["120000"]:
        target = os.path.normpath(
            os.path.join(os.path.dirname(path), git("show", f"{base}:{path}"))
        )
        if target.startswith(".."):
            raise ValueError(f"{path} links outside the repository")
        path = target
    return git("show", f"{base}:{path}")


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
                before = test_methods(base_source(base, base_path))
            except (subprocess.CalledProcessError, SyntaxError, ValueError):
                before = {}  # fails closed: every test in the file is new
        for tid, (fp, first, last) in head.items():
            if tid not in before:
                new.append((head_path, tid, fp, pins(source, first, last)))
        gone += [
            (base_path, t, fp) for t, (fp, _, _) in before.items() if t not in head
        ]

    def key(test_id, fingerprint):
        return test_id.rsplit(".", 1)[0], fingerprint

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


def subclass_files():
    """{test file at HEAD: names its classes inherit from}, to find runners elsewhere."""
    out = {}
    for path in git("ls-files", "-z").split("\0"):
        if not TEST_FILE_RE.search(path):
            continue
        try:
            tree = ast.parse(
                pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
            )
        except (OSError, SyntaxError, ValueError):
            continue
        bases = [
            b for n in ast.walk(tree) if isinstance(n, ast.ClassDef) for b in n.bases
        ]
        out[path] = {getattr(b, "id", getattr(b, "attr", "")) for b in bases}
    return out


def run_one(cwd, path, test_id, mode, out, naming="package", stubs=(), others=()):
    """(verdict, detail, names the test module resolved) of one test run alone."""
    qualname, method = test_id.rsplit(".", 1)
    env = dict(os.environ, RED_FIRST_OUT=str(out))
    cmd = [sys.executable, "-c", DRIVER, path, qualname, method, mode, naming]
    cmd += [json.dumps(list(stubs)), json.dumps(list(others))]
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=RUN_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return "timeout", f"after {RUN_TIMEOUT}s", []
    try:
        result = json.loads(pathlib.Path(out).read_text())
    except (OSError, ValueError, KeyError, TypeError):
        tail = (r.stderr.strip().splitlines() or ["no output"])[-1][:200]
        return "error", f"no result: {tail}", []
    ran = [v for v in result["verdicts"] if v[0] != "skipped"] or result["verdicts"]
    verdict, detail = min(ran, key=lambda v: ORDER.index(v[0]))
    return verdict, detail, result["resolved"]


def verdicts(worktree, path, test_id, others, out):
    """(verdict at HEAD, detail, verdict on the base, detail) for one new test."""
    naming = "package"
    at_head, head_why, resolved = run_one(
        ".", path, test_id, "head", out("head"), naming, others=others
    )
    if head_why in (
        "module did not load: ModuleNotFoundError",
        "module did not load: ImportError",
    ):
        flat = run_one(".", path, test_id, "head", out("flat"), "flat", others=others)
        if not flat[1].startswith(
            "module did not load"
        ):  # named as `discover -s <dir>` would
            naming, (at_head, head_why, resolved) = "flat", flat
    if at_head == "not-a-test":
        return at_head, head_why, "", ""
    on_base, why, _ = run_one(
        worktree, path, test_id, "base", out("base"), naming, resolved, others
    )
    return at_head, head_why, on_base, why


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


def prepare_worktree(worktree, base, files, entries):
    """The base's code with the PR's test files, test-support files and `__init__.py`s."""
    git("worktree", "add", "--detach", "-q", str(worktree), base)
    copies = [head for head, _ in files if head] + support_files(entries)
    for path in list(copies):
        for parent in pathlib.PurePosixPath(path).parents:
            init = parent / "__init__.py"
            if (
                str(parent) != "."
                and pathlib.Path(init).exists()
                and not (worktree / init).exists()
            ):
                copies.append(str(init))
    for path in copies:
        dest = worktree / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink():
            dest.unlink()
        shutil.copyfile(path, dest)


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
    entries = changes(base)
    files = changed_test_files(entries)
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
    inherits = subclass_files()
    try:
        prepare_worktree(worktree, base, files, entries)
        for n, (path, test_id, reasons) in enumerate(tests):
            simple = test_id.rsplit(".", 1)[0].rsplit(".", 1)[-1]
            others = sorted(
                p for p, names in inherits.items() if p != path and simple in names
            )
            at_head, head_why, on_base, why = verdicts(
                worktree, path, test_id, others, lambda run: tmp / f"{n}-{run}.json"
            )
            if at_head == "not-a-test":
                line = f"  {path} {test_id}: not a test (no TestCase runs it)"
            else:
                line, found = judge(
                    path, test_id, reasons, on_base, why, at_head, head_why
                )
                violations += found
            print(line)
            summary.append(line)
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
