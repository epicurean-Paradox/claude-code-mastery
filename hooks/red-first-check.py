#!/usr/bin/env python3
"""red-first-check.py -- every NEW test must fail against the merge base (LESSONS Lesson 28).

    python3 red-first-check.py --base <merge-base-sha>

Finds the unittest test methods (`test*` in a class, nested classes and if/try/with blocks
included, in a `test_*.py` file) that exist at HEAD but not at the base. It parses both
versions; a renamed file is compared with its source, and a symlinked base file is read
through its link. A test that keeps its class, decorators, signature, body and context
(the class's other members, the module's statements outside definitions, the definitions
it uses, the package behind relative imports) under a new name or in another file is a
rename, not new -- one gone test pairs with one new test, never with several. For each new
test it:

  1. runs it at HEAD: it must pass -- a test that never passes proves nothing;
  2. runs it against the BASE's code: a throwaway worktree with the PR's test files, its
     changed files under test-support directories, the `__init__.py` files the base lacks
     and the gitignored modules the checkout has, minus the test files the PR deletes. It
     must fail or error there -- a test that passes on the old code cannot see the defect
     the change fixes.

Each run loads exactly that test in its own interpreter, imports its module as discovery
would (package.module, else from the file's own directory, decided at HEAD), and records
the test's own outcome apart from class and module fixtures. The test runs in every
module-level TestCase that inherits the method unchanged, as discovery runs it, including
subclasses in other test files (found by following inheritance through imports); with none
it is not a test. On the base it counts as red if any runner is red, leaving out runner
classes the PR adds while an older one exists.

On the base the module is first imported as it is. When an ImportError or AttributeError
escapes for a name HEAD defines in the repository (`from lib import new`, `lib.NEW`, a
module the PR adds), that name is stubbed and the import retried, so one new name does not
turn every test in the file red. A stub absorbs any use while modules import (a derived
constant, a decorator, a base class) and raises once tests run; a test that names one
directly, or a module global derived from one, counts as an error.

The escape: a test that legitimately passes on the base (a mutant-killer, an over-strictness
guard), or is skipped where the check runs, carries a COMMENT on its `def` line or in its body,

    # red-first: pins <what wrong behaviour it catches>   (at least 10 characters of reason)

-- not a string, not a docstring. Every pin is printed, so a reviewer sees each one.

Verdicts on the base: red (an assertion failed), error (an exception, a failing class or
module fixture, a missing name: printed so a reviewer can confirm it is red for the right
reason), timed out (counts as red), green (also an unexpected success: the body passed),
skipped or expected-failure (indeterminate: a violation unless pinned), not collected (the
class or method does not exist at run time: a violation).

Limits: a changed (not new) test is not re-checked; tests inherited by a new subclass and
methods generated at runtime are not seen; a test whose behaviour depends on its own name
can pass as a rename; subTest granularity is the whole test; a dependency the PR adds from
outside the repository cannot load on the base, so every test importing it counts as red;
changed files outside test-support directories stay at the base's version; an editable
install that points at the HEAD checkout imports HEAD's code on the base; a test can always
tell it runs in the base worktree; the runner is unittest. Exit 0 clean, 1 a violation,
2 usage (unknown base, not a repo).
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
# Changed files under these directories are test code or data, copied into the base. Not
# `test` or `testing`: those are often product packages (django.test, numpy.testing).
SUPPORT_DIRS = set(
    os.environ.get(
        "RED_FIRST_SUPPORT_DIRS", "tests,fixtures,testdata,test-fixtures,test_fixtures"
    ).split(",")
)
GENERATED = (".py", ".pyi", ".so", ".pyd")  # gitignored modules the checkout may hold
BLOCKS = (ast.If, ast.Try, ast.With) + (
    (ast.TryStar,) if hasattr(ast, "TryStar") else ()
)
DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
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
# (head/base). The result and config files arrive in the environment. Everything lives in
# a function, so a test cannot reach the driver's state through __main__.
DRIVER = r'''
def driver():
    import ast, builtins, importlib, json, os, re, symtable, sys, types, unittest, warnings

    out = open(os.environ.pop("RED_FIRST_OUT"), "w")
    with open(os.environ.pop("RED_FIRST_CONFIG")) as fh:
        config = json.load(fh)
    path, qualname, method, mode = sys.argv[1:]
    del sys.argv[1:]
    root = os.path.realpath(os.getcwd())
    sys.path[0] = root  # absolute, as under `python -m unittest`: survives a chdir
    target_file = os.path.realpath(os.path.join(root, path))
    head_attrs = config.get("attrs", {})  # base: {module: {"names", "package"}} at HEAD
    namings = dict(config.get("namings", {}))
    state = {"armed": False}
    from_stubs, attr_stubs, module_stubs, patched = set(), set(), set(), []

    def in_project(module):
        f = getattr(module, "__file__", None)
        return bool(f) and os.path.realpath(f).startswith(root + os.sep)

    def project_attrs():
        if mode != "head":
            return {}
        return {
            name: {"names": sorted(k for k in vars(m) if isinstance(k, str)), "package": hasattr(m, "__path__")}
            for name, m in list(sys.modules.items())
            if in_project(m)
        }

    def finish(*verdicts):
        json.dump({"verdicts": verdicts, "attrs": project_attrs(), "namings": namings}, out)
        out.close()
        os._exit(0)

    class MissingOnBase(Exception):
        pass

    class Missing:
        """A name only HEAD defines. While modules import it absorbs every use (a derived
        constant, a decorator, a base class, a dict key); once tests run any use raises."""

        def __init__(self, name):
            object.__setattr__(self, "_name", name)

        def __repr__(self):
            return f"<missing on base: {self._name}>"

        def _use(self, *args, **kwargs):
            if state["armed"]:
                raise MissingOnBase(f"missing on base: {self._name}")
            return self

        def __call__(self, *args, **kwargs):
            self._use()
            if len(args) == 1 and not kwargs and isinstance(args[0], (type, types.FunctionType)):
                return args[0]  # a decorator: keep what it decorates
            return self

        def __mro_entries__(self, bases):
            return ()  # a base class only HEAD defines: left out

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

        __setattr__ = __getitem__ = __setitem__ = __contains__ = _use
        __eq__ = __ne__ = __lt__ = __le__ = __gt__ = __ge__ = __neg__ = __pos__ = _use
        __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = _use
        __rtruediv__ = __floordiv__ = __mod__ = __pow__ = __or__ = __ror__ = __and__ = _use

    class Proxy:
        """The module of one `from module import ...` statement, plus its stubbed names."""

        def __init__(self, module, stubs):
            self.__dict__.update(stubs)
            self.__dict__["_red_first_module"] = module

        def __getattr__(self, attr):
            return getattr(self.__dict__["_red_first_module"], attr)

    def patch(module):
        """PEP 562 __getattr__ on a module for its stubbed attributes, while modules import."""
        names = {x for m, x in attr_stubs if m == module.__name__}
        if not names or any(m is module for m, _ in patched):
            return
        original = module.__dict__.get("__getattr__")

        def __getattr__(attr):
            if attr in names and not state["armed"]:
                return Missing(f"{module.__name__}.{attr}")
            if original:
                return original(attr)
            raise AttributeError(f"module {module.__name__!r} has no attribute {attr!r}")

        patched.append((module, original))
        module.__getattr__ = __getattr__

    real_import = builtins.__import__

    def lenient_import(name, globals=None, locals=None, fromlist=(), level=0):
        module = real_import(name, globals, locals, fromlist, level)
        for m in {m for m, _ in attr_stubs}:
            if m in sys.modules:
                patch(sys.modules[m])
        stubs = {
            a: Missing(f"{module.__name__}.{a}")
            for a in fromlist or ()
            if a != "*" and (module.__name__, a) in from_stubs and not hasattr(module, a)
        }
        return Proxy(module, stubs) if stubs else module

    def install_module_stubs():
        for name in module_stubs:
            if name not in sys.modules:
                stub = types.ModuleType(name)
                for attr in head_attrs[name]["names"]:
                    if not attr.startswith("__"):
                        setattr(stub, attr, Missing(f"{name}.{attr}"))
                if head_attrs[name]["package"]:
                    stub.__path__ = []
                sys.modules[name] = stub
                parent, _, child = name.rpartition(".")
                if parent in sys.modules:
                    setattr(sys.modules[parent], child, stub)

    def learn(exc):
        """Stub the name whose absence on the base made `exc` escape; False if none."""
        msg = str(exc)
        if isinstance(exc, ModuleNotFoundError):
            if exc.name in head_attrs and exc.name not in module_stubs:
                module_stubs.add(exc.name)
                return True
            return False
        found = None
        if isinstance(exc, ImportError):
            m = re.search(r"cannot import name '([^']+)' from '([^']+)'", msg)
            found, kind = (m and (m.group(2), m.group(1))), from_stubs
        elif isinstance(exc, AttributeError):
            m = re.search(r"module '([^']+)' has no attribute '([^']+)'", msg)
            found, kind = (m and (m.group(1), m.group(2))), attr_stubs
        if found and found[1] in head_attrs.get(found[0], {}).get("names", ()) and found not in kind:
            kind.add(found)
            return True
        return False

    def locate(rel, naming):
        """(top-level directory, module name) as discovery would import the file."""
        file = os.path.join(root, rel)
        parts, top = [os.path.splitext(os.path.basename(file))[0]], os.path.dirname(file)
        while naming == "package" and top != root and os.path.exists(os.path.join(top, "__init__.py")):
            if not os.path.basename(top).isidentifier():
                break
            parts.insert(0, os.path.basename(top))
            top = os.path.dirname(top)
        return top, ".".join(parts)

    def load(rel, naming, first):
        """Import a test file; on the base, stub what HEAD defines and retry."""
        top, name = locate(rel, naming)
        if top not in sys.path:
            sys.path.insert(0 if first else 1, top)
        exc = None
        for _ in range(64):
            install_module_stubs()
            builtins.__import__ = lenient_import
            try:
                return importlib.import_module(name), None
            except BaseException as e:  # Python drops the modules that failed
                exc = e
                if mode != "base" or not learn(e):
                    return None, exc
            finally:
                builtins.__import__ = real_import
        return None, exc

    def load_file(rel, first=False):
        if mode == "base":
            return load(rel, namings.get(rel, "package"), first)
        module, exc = load(rel, "package", first)
        if module is None and isinstance(exc, ImportError) and locate(rel, "package") != locate(rel, "flat"):
            flat = load(rel, "flat", first)
            if flat[0] is not None:  # named as `discover -s <dir>` would
                namings[rel] = "flat"
                return flat
        namings[rel] = "package"
        return module, exc

    module, exc = load_file(path, first=True)
    if module is None:
        finish(["error", f"module did not load: {type(exc).__name__}"])
    loaded, load_errors = [module], []
    for other in config.get("others", []):
        m, e = load_file(other)
        if m is None:
            load_errors.append(f"{other}: module did not load: {type(e).__name__}")
        elif m is not module:
            loaded.append(m)
    state["armed"] = True  # patched modules now answer as the base would

    derived = {k: v._name for k, v in vars(module).items() if isinstance(v, Missing)}
    if derived:  # a test that names a missing name cannot run on the real base
        with open(target_file, encoding="utf-8", errors="replace") as fh:
            table = symtable.symtable(fh.read(), path, "exec")
        for part in qualname.split("."):
            table = next((t for t in table.get_children() if t.get_name() == part and t.get_type() == "class"), None)
            if table is None:
                break
        todo = [t for t in table.get_children() if t.get_name() == method] if table else []
        used = set()
        while todo:
            t = todo.pop()
            used |= {s.get_name() for s in t.get_symbols() if s.is_referenced() and s.is_global()}
            todo += [c for c in t.get_children() if c.get_type() != "class"]
        hit = sorted({derived[n] for n in used if n in derived})
        if hit:
            finish(["error", "missing on base: " + ", ".join(hit)])

    def source(cls):
        f = getattr(sys.modules.get(cls.__module__), "__file__", None)
        return os.path.realpath(f) if f else None

    def same(cls):
        return cls.__qualname__ == qualname and source(cls) == target_file

    classes = [c for m in loaded for c in vars(m).values() if isinstance(c, type)]
    target = module
    for part in qualname.split("."):
        target = getattr(target, part, None)
    if not (isinstance(target, type) and same(target)):  # e.g. a base deleted after use
        target = next((b for c in classes for b in c.__mro__ if same(b)), None)
    if target is None:
        finish(["uncollected", ""])

    runners, seen = [], set()
    for c in classes:  # what discovery runs: module-level TestCases that inherit the method
        owner = next((b for b in c.__mro__ if method in vars(b)), None)
        if issubclass(c, unittest.TestCase) and owner is not None and same(owner) and callable(getattr(c, method, None)):
            if (source(c), c.__qualname__) not in seen:
                seen.add((source(c), c.__qualname__))
                runners.append(c)
    if mode == "base":  # a runner the PR adds tests the PR's code, not the old one
        new = set(config.get("new_classes", []))
        old = [c for c in runners if f"{os.path.relpath(source(c), root)}::{c.__qualname__}" not in new]
        runners = old or runners
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

        def addUnexpectedSuccess(self, test):  # the body passed; the run as a whole fails
            self.own[test] = ["green" if mode == "base" else "red", "unexpected success"]

        def addSubTest(self, test, subtest, err):
            if err is None:
                self.subpassed.add(test)
            else:
                failed = issubclass(err[0], test.failureException)
                self.own[test] = ["red", ""] if failed else ["error", self.why(err)]

    verdicts = []
    for runner in runners:
        try:
            case = runner(method)
        except ValueError:
            verdicts.append(["uncollected", ""])
            continue
        except Exception as e:
            verdicts.append(["error", f"{type(e).__name__} building the test"])
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


driver()
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


def is_support(path):
    """Test code or data: under a test-support directory, or a conftest.py."""
    return bool(SUPPORT_DIRS & set(path.split("/")[:-1])) or path.endswith(
        "conftest.py"
    )


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


def _names(nodes):
    return {n.id for node in nodes for n in ast.walk(node) if isinstance(n, ast.Name)}


def _module_context(tree, path, names, own_class):
    """The module's statements outside definitions, the definitions `names` reach
    (followed transitively), and the package behind any relative import."""
    definitions = collections.defaultdict(list)
    for node in _walk(tree.body, DEFINITIONS):
        definitions[node.name].append(node)
    dumps = [ast.dump(n) for n in tree.body if not isinstance(n, DEFINITIONS)]
    if any(isinstance(n, ast.ImportFrom) and n.level for n in ast.walk(tree)):
        dumps.append(f"package:{os.path.dirname(path)}")
    seen, todo = {own_class}, set(names)
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        for node in definitions.get(name, ()):
            dumps.append(ast.dump(node))
            todo |= _names([node])
    return "|".join(sorted(dumps))


def test_methods(source, path):
    """{"Class.test_x": (rename key, first line, last line)}; raises SyntaxError."""
    tree = ast.parse(source)
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
                own = [*item.decorator_list, item.args, *item.body]
                names = _names([item, *heading, *members])
                context = _module_context(tree, path, names, qualname.split(".")[0])
                found[f"{qualname}.{item.name}"] = (
                    "#".join(("|".join(map(ast.dump, own)), class_context, context)),
                    item.lineno,
                    item.end_lineno,
                )
    return found


def class_names(source):
    return {q for q, _ in _test_classes(ast.parse(source).body)}


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
    """([(path, test_id, pin reasons)], [renamed ids], [parse errors], [new classes])."""
    new, gone, errors, new_classes = [], [], [], []
    for head_path, base_path in files:
        head, source, head_classes = {}, "", set()
        if head_path:
            source = pathlib.Path(head_path).read_text(
                encoding="utf-8", errors="replace"
            )
            try:
                head, head_classes = (
                    test_methods(source, head_path),
                    class_names(source),
                )
            except SyntaxError as exc:
                errors.append(
                    f"{head_path}:RED-FIRST:does not parse at HEAD (line {exc.lineno})"
                )
                continue
        before, base_classes = {}, set()
        if base_path:
            try:
                text = base_source(base, base_path)
                before, base_classes = test_methods(text, base_path), class_names(text)
            except (subprocess.CalledProcessError, SyntaxError, ValueError):
                before = {}  # fails closed: every test in the file is new
        new_classes += [
            f"{head_path}::{q}" for q in sorted(head_classes - base_classes)
        ]
        # In a moved file, a test whose context changed (another package behind its relative
        # imports, say) is new; in a file that stays put an edited test is a changed one.
        moved = bool(head_path and base_path and head_path != base_path)
        kept = {
            t
            for t in head
            if t in before and not (moved and head[t][0] != before[t][0])
        }
        for tid, (fp, first, last) in head.items():
            if tid not in kept:
                new.append((head_path, tid, fp, pins(source, first, last)))
        gone += [
            (base_path, t, fp) for t, (fp, _, _) in before.items() if t not in kept
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
    return tests, renamed, errors, new_classes


def _base_ref(expr, path, imported):
    """What a base-class expression names: ("file", path, qualname) for a class of this
    file, ("module", last module name part, qualname) for an imported one, else None."""
    parts = []
    while isinstance(expr, ast.Attribute):
        parts.insert(0, expr.attr)
        expr = expr.value
    if not isinstance(expr, ast.Name):
        return None
    if expr.id not in imported:
        return "file", path, ".".join([expr.id, *parts])
    module, name = imported[expr.id]
    qualname = ".".join([name, *parts] if name else parts)
    return ("module", module.rsplit(".", 1)[-1], qualname) if qualname else None


def class_graph():
    """{test file at HEAD: [(class qualname, [base refs])]}, to find runners elsewhere."""
    graph = {}
    for path in git("ls-files", "-z").split("\0"):
        if not TEST_FILE_RE.search(path):
            continue
        try:
            tree = ast.parse(
                pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
            )
        except (OSError, SyntaxError, ValueError):
            continue
        imported = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imported[a.asname or a.name.split(".")[0]] = (
                        a.name if a.asname else a.name.split(".")[0],
                        None,
                    )
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    imported[a.asname or a.name] = (
                        node.module or a.name,
                        node.module and a.name,
                    )
        graph[path] = [
            (q, [_base_ref(b, path, imported) for b in cls.bases])
            for q, cls in _test_classes(tree.body)
        ]
    return graph


def runner_files(graph, path, qualname):
    """Other test files whose classes inherit `qualname`, through any chain of classes."""
    relevant, files, changed = {(path, qualname)}, set(), True
    while changed:
        changed = False
        for f, classes in graph.items():
            for q, bases in classes:
                if (f, q) in relevant:
                    continue
                if any(
                    ref
                    and (
                        (ref[0] == "file" and (ref[1], ref[2]) in relevant)
                        or (
                            ref[0] == "module"
                            and any(
                                pathlib.PurePosixPath(p).stem == ref[1] and r == ref[2]
                                for p, r in relevant
                            )
                        )
                    )
                    for ref in bases
                ):
                    relevant.add((f, q))
                    files.add(f)
                    changed = True
    return sorted(files - {path})


def run_one(cwd, path, test_id, mode, scratch, config):
    """(verdict, detail, the driver's record) of one test run alone; see DRIVER."""
    qualname, method = test_id.rsplit(".", 1)
    out, config_file = scratch.with_suffix(".json"), scratch.with_suffix(".config")
    config_file.write_text(json.dumps(config))
    env = dict(os.environ, RED_FIRST_OUT=str(out), RED_FIRST_CONFIG=str(config_file))
    cmd = [sys.executable, "-c", DRIVER, path, qualname, method, mode]
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
        return "timeout", f"after {RUN_TIMEOUT}s", {}
    try:
        record = json.loads(out.read_text())
    except (OSError, ValueError):
        tail = (r.stderr.strip().splitlines() or ["no output"])[-1][:200]
        return "error", f"no result: {tail}", {}
    ran = [v for v in record["verdicts"] if v[0] != "skipped"] or record["verdicts"]
    verdict, detail = min(ran, key=lambda v: ORDER.index(v[0]))
    return verdict, detail, record


def verdicts(worktree, path, test_id, others, new_classes, scratch):
    """(verdict at HEAD, detail, verdict on the base, detail) for one new test."""
    config = {"others": others}
    at_head, head_why, record = run_one(
        ".", path, test_id, "head", scratch / "head", config
    )
    if at_head == "not-a-test":
        return at_head, head_why, "", ""
    config.update(
        attrs=record.get("attrs", {}),
        namings=record.get("namings", {}),
        new_classes=new_classes,
    )
    on_base, why, _ = run_one(worktree, path, test_id, "base", scratch / "base", config)
    return at_head, head_why, on_base, why


def judge(path, test_id, reasons, on_base, why, at_head, head_why):
    """(summary line, [violations]) for one new test."""
    where = f"{path}:RED-FIRST:{test_id}"
    note = NOTES[on_base].format(why=why)
    if why and "{why}" not in NOTES[on_base]:
        note += f" ({why})"
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
    """The base's code with the PR's test files and test-support files, the `__init__.py`
    files the base lacks and the gitignored modules the checkout has; minus deleted tests."""
    git("worktree", "add", "--detach", "-q", str(worktree), base)
    copies = [head for head, _ in files if head]
    copies += [dst for status, _, dst in entries if status != "D" and is_support(dst)]
    ignored = git(
        "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory"
    )
    copies += [
        p
        for p in ignored.split("\0")
        if p.endswith(GENERATED) and not (worktree / p).exists()
    ]
    for path in list(copies):
        for parent in pathlib.PurePosixPath(path).parents:
            init = parent / "__init__.py"
            if (
                str(parent) != "."
                and pathlib.Path(init).exists()
                and not (worktree / init).exists()
            ):
                copies.append(str(init))
    for status, src, _ in entries:  # what the PR deletes from the test side
        if status == "D" and (TEST_FILE_RE.search(src) or is_support(src)):
            (worktree / src).unlink(missing_ok=True)
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
    tests, renamed, violations, new_classes = new_tests(base, files)
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
    graph = class_graph()
    try:
        prepare_worktree(worktree, base, files, entries)
        for n, (path, test_id, reasons) in enumerate(tests):
            others = runner_files(graph, path, test_id.rsplit(".", 1)[0])
            scratch = tmp / str(n)
            scratch.mkdir()
            at_head, head_why, on_base, why = verdicts(
                worktree, path, test_id, others, new_classes, scratch
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
