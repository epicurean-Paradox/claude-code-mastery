#!/usr/bin/env python3
"""red-first-check.py -- every NEW test must fail against the merge base (LESSONS Lesson 28).

    python3 red-first-check.py --base <merge-base-sha>

Finds the unittest test methods (`test*` in a class, nested classes and if/try/with blocks
included, in a `test_*.py` file) that exist at HEAD but not at the base. It parses both
versions; a renamed file is compared with its source, and a symlinked base file is read
through its link. A test that keeps its class, decorators, signature, body and context
(the class's other members, the module statements it reaches, the package behind a
relative import among them) under a new name or in another file is a rename, not new --
one gone test pairs with one new test, never with several; a class renamed with the same
heading and body is not new either. For each new test it:

  1. runs it at HEAD: it must pass -- a test that never passes proves nothing;
  2. runs it against the BASE's code: a throwaway worktree with the PR's test files, its
     changed files under test-support directories (`tests/`, `fixtures/`, ...; `test/`
     when it holds test files), the `__init__.py` files the base lacks and the gitignored
     modules the checkout holds (single files and packages in ignored directories, at
     most 5000), minus the test and support files the PR deletes. It must fail or error
     there -- a test that passes on the old code cannot see the defect the change fixes.

Each run loads exactly that test in its own interpreter, imports its module as discovery
would (package.module, else from the file's own directory, decided per file at HEAD), and
records the test's own outcome apart from class and module fixtures. The test runs in
every module-level TestCase that inherits the method unchanged, as discovery runs it,
including subclasses in other test files (any test file with a class whose base may be
the same class by name); with none it is not a test -- unless such a file exists, which
is a violation. On the base it counts as red if any runner is red, leaving out runner
classes the PR adds while an older one exists.

On the base the test module runs one top-level statement at a time. When an ImportError
or AttributeError escapes for a name HEAD defines in the repository (`from lib import new`,
`lib.NEW`, a module the PR adds), that name -- with every other name HEAD's module has and
the base's lacks -- is stubbed for the module it escaped from, and the import retried; a
fallback import of any shape keeps working, and code under test never sees a stub. A
statement that names a stub is skipped and a statement that still raises is stubbed; a
stub absorbs any use while the module imports and raises once tests run. A test counts
as an error when its class's heading or body, its decorators or defaults, or a module
global it reaches (through its fixtures, `self.` helpers and module functions) depends on
a stub or on a failed statement.

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
can pass as a rename; subTest granularity is the whole test; changed files outside
test-support directories stay at the base's version; a gitignored generated module is
HEAD's build, so a fix in generated code is copied into the base too (pin such a test);
a class body that touches a stub ties every test of that class to it; an editable install
that points at the HEAD checkout imports HEAD's code on the base; a test can always tell
it runs in the base worktree, and reach the driver; the runner is unittest. Exit 0 clean,
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
# Changed files under these directories are test code or data, copied into the base. Not
# `test` or `testing`: those are often product packages (django.test, numpy.testing).
SUPPORT_DIRS = set(
    os.environ.get(
        "RED_FIRST_SUPPORT_DIRS", "tests,fixtures,testdata,test-fixtures,test_fixtures"
    ).split(",")
)
GENERATED = (".py", ".pyi", ".so", ".pyd")  # gitignored modules the checkout may hold
MAX_GENERATED = 5000
SKIP_DIRS = {
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    "build",
    "dist",
    "site-packages",
}
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
    import __future__, ast, builtins, importlib, importlib.util, json, os, re, symtable
    import sys, types, unittest, warnings

    out = open(os.environ.pop("RED_FIRST_OUT"), "w")
    with open(os.environ.pop("RED_FIRST_CONFIG")) as fh:
        config = json.load(fh)
    path, qualname, method, mode = sys.argv[1:]
    del sys.argv[1:]
    root = os.path.realpath(os.getcwd())
    sys.path[0] = root  # absolute, as under `python -m unittest`: survives a chdir
    code_file = os.path.join(root, path)
    target_file = os.path.realpath(code_file)
    head_attrs = config.get("attrs", {})  # base: {module: {"names", "package"}} at HEAD
    namings = dict(config.get("namings", {}))
    state = {"armed": False, "module": None}
    # Learned stubs, each scoped to the module whose import escaped: (importer, module, name)
    # for a from-import or an attribute, (importer, module) for a module the base lacks.
    from_stubs, attr_stubs, module_stubs = set(), set(), set()
    patched, stub_cache, stub_modules = set(), {}, set()
    touched = set()  # test-file lines running when a stub was used during imports
    derived, marked = {}, {}  # names / class or method qualnames -> what they miss
    with open(target_file, encoding="utf-8", errors="replace") as fh:
        source_text = fh.read()
    tree = ast.parse(source_text)

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

    def touch():
        """Record where the test file uses a stub: its innermost module or class-body frame
        (not a function's), as (scope name, line)."""
        f = sys._getframe(1)
        while f is not None:
            if f.f_code.co_filename == code_file and not f.f_code.co_flags & 1:  # CO_OPTIMIZED
                touched.add((f.f_code.co_name, f.f_lineno))
                return
            f = f.f_back

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
            touch()
            return self

        def __call__(self, *args, **kwargs):
            self._use()
            if len(args) == 1 and not kwargs and isinstance(args[0], (type, types.FunctionType)):
                return args[0]  # a decorator: keep what it decorates
            return self

        def __mro_entries__(self, bases):
            self._use()
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

    def stub_module(name):
        if name not in stub_cache:
            stub = types.ModuleType(name)
            info = head_attrs.get(name, {"names": [], "package": True})
            for attr in info["names"]:
                if not attr.startswith("__"):
                    setattr(stub, attr, Missing(f"{name}.{attr}"))
            if info["package"]:
                stub.__path__ = []
            stub_cache[name] = stub
            stub_modules.add(id(stub))
        return stub_cache[name]

    def patch(module):
        """PEP 562 __getattr__ answering a stubbed attribute to the module that needs it."""
        if id(module) in patched:
            return
        original = module.__dict__.get("__getattr__")

        def __getattr__(attr):
            accessor = sys._getframe(1).f_globals.get("__name__")
            if not state["armed"] and (accessor, module.__name__, attr) in attr_stubs:
                touch()
                return Missing(f"{module.__name__}.{attr}")
            if original:
                return original(attr)
            raise AttributeError(f"module {module.__name__!r} has no attribute {attr!r}")

        patched.add(id(module))
        module.__getattr__ = __getattr__

    real_import = builtins.__import__

    def lenient_import(name, globals=None, locals=None, fromlist=(), level=0):
        importer = (globals or {}).get("__name__")
        absolute = name
        if level:
            try:
                absolute = importlib.util.resolve_name("." * level + name, (globals or {}).get("__package__"))
            except (ImportError, ValueError):
                pass
        if any(i == importer and (absolute == m or absolute.startswith(m + ".")) for i, m in module_stubs):
            if not fromlist and "." in absolute:  # `import a.b`: binds a
                return real_import(absolute.split(".")[0], globals, locals, (), 0)
            return stub_module(absolute)
        module = real_import(name, globals, locals, fromlist, level)
        for _, m, _ in attr_stubs:
            if m in sys.modules:
                patch(sys.modules[m])
        stubs = {
            a: Missing(f"{module.__name__}.{a}")
            for a in fromlist or ()
            if a != "*" and (importer, module.__name__, a) in from_stubs and not hasattr(module, a)
        }
        return Proxy(module, stubs) if stubs else module

    def learn(exc):
        """Stub what the base lacks behind `exc`, for the module it escaped from; False if
        there is nothing HEAD defines to stub."""
        importer, tb = None, exc.__traceback__
        while tb is not None:  # the last frame outside the driver (its code is "<string>")
            if tb.tb_frame.f_code.co_filename != "<string>":
                importer = tb.tb_frame.f_globals.get("__name__")
            tb = tb.tb_next
        if isinstance(exc, ModuleNotFoundError):
            if exc.name in head_attrs and (importer, exc.name) not in module_stubs:
                module_stubs.add((importer, exc.name))
                return True
            return False
        if isinstance(exc, ImportError):
            m = re.search(r"cannot import name '([^']+)' from '([^']+)'", str(exc))
            found, kind = (m and (m.group(2), m.group(1))), from_stubs
        elif isinstance(exc, AttributeError):
            m = re.search(r"module '([^']+)' has no attribute '([^']+)'", str(exc))
            found, kind = (m and (m.group(1), m.group(2))), attr_stubs
        else:
            return False
        if not found or found[1] not in head_attrs.get(found[0], {}).get("names", ()):
            return False
        base_module = sys.modules.get(found[0])
        new = {(importer, *found)}  # with every other name HEAD has and the base lacks
        new |= {
            (importer, found[0], n)
            for n in head_attrs[found[0]]["names"]
            if base_module is not None and not n.startswith("__") and n not in vars(base_module)
        }
        if new <= kind:
            return False
        kind |= new
        for _, m, _ in attr_stubs:
            if m in sys.modules:
                patch(sys.modules[m])
        return True

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

    def import_name(name):
        """Import a module by name; on the base, stub what HEAD defines and retry."""
        exc = None
        for _ in range(64):
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
        """Import a test file, deciding at HEAD how discovery names it."""
        naming = namings.get(rel, "package")
        for attempt in ("package", "flat") if mode == "head" else (naming,):
            top, name = locate(rel, attempt)
            if top not in sys.path:
                sys.path.insert(0 if first else 1, top)
            module, exc = import_name(name)
            namings[rel] = attempt
            if module is not None or not isinstance(exc, ImportError) or locate(rel, "flat") == (top, name):
                return module, exc
        return module, exc

    DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)

    def bound(stmt):
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return [stmt.name]
        names = []
        for n in ast.walk(stmt):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                names.append(n.id)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                names += [(a.asname or a.name).split(".")[0] for a in n.names if a.name != "*"]
        return names

    def refers(g, nodes):
        """What a stubbed or derived name, or a stubbed attribute, in `nodes` misses."""
        for node in nodes:
            for n in ast.walk(node):
                if isinstance(n, ast.Name) and n.id in derived:
                    return derived[n.id]
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
                    owner = g.get(n.value.id)
                    owner_name = owner.__name__ if isinstance(owner, types.ModuleType) else None
                    if owner_name and (state["module"], owner_name, n.attr) in attr_stubs:
                        return f"{owner_name}.{n.attr}"
        return None

    def hit(start, stop, scope="<module>"):
        return any(name == scope and start <= line < stop for name, line in touched)

    def mark_class(g, cls, prefix):
        qual = prefix + cls.name
        start = min([cls.lineno] + [d.lineno for d in cls.decorator_list])
        first = cls.body[0].lineno if cls.body else cls.lineno + 1
        why = refers(g, [*cls.bases, *cls.keywords, *cls.decorator_list])
        why = why or (hit(start, first) and f"line {cls.lineno}: a base or decorator")
        for item in cls.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                deco = item.decorator_list
                start = deco[0].lineno if deco else item.lineno
                defaults = [*item.args.defaults, *[d for d in item.args.kw_defaults if d]]
                d = refers(g, [*deco, *defaults]) or (hit(start, item.lineno + 1, cls.name) and f"line {start}: a decorator or default")
                if d:
                    marked[f"{qual}.{item.name}"] = d
            elif isinstance(item, ast.ClassDef):
                mark_class(g, item, qual + ".")
            else:
                why = why or refers(g, [item]) or (hit(item.lineno, item.end_lineno + 1, cls.name) and f"line {item.lineno}")
        if why:
            marked[qual] = why

    def run_statement(g, stmt, flags):
        code = compile(ast.Module(body=[stmt], type_ignores=[]), code_file, "exec", flags=flags, dont_inherit=True)
        why = None if isinstance(stmt, DEFS) else refers(g, [stmt])
        error = None
        for _ in range(64 if why is None else 0):
            touched.clear()
            try:
                exec(code, g)
                error = None
                break
            except BaseException as e:
                error = e
                if not learn(e):
                    break
                why = None if isinstance(stmt, DEFS) else refers(g, [stmt])
                if why:  # it now names a stub: skip it, as it never runs on the real base
                    break
        if why is None and error is not None:
            why = f"line {stmt.lineno}: {type(error).__name__}"
        names = bound(stmt)
        if why is not None:
            for n in names:
                g[n] = Missing(why)
                derived[n] = why
            if isinstance(stmt, ast.ClassDef):
                marked[stmt.name] = why
            return
        for n, v in list(g.items()):  # bound to a stub, a star import's names included
            if n not in derived and isinstance(v, Missing):
                derived[n] = v._name
            elif n not in derived and id(v) in stub_modules:
                derived[n] = v.__name__
        if isinstance(stmt, ast.ClassDef):
            mark_class(g, stmt, "")
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            deco = stmt.decorator_list
            d = deco and (refers(g, deco) or (hit(deco[0].lineno, stmt.lineno) and f"line {deco[0].lineno}: a decorator"))
            if d:
                derived[stmt.name] = d
        elif not isinstance(stmt, (ast.Import, ast.ImportFrom)) and hit(stmt.lineno, stmt.end_lineno + 1):
            for n in names:  # built from a stub while importing
                derived.setdefault(n, f"line {stmt.lineno}")

    def run_module(rel):
        """The test module on the base, one top-level statement at a time: a statement that
        names a stub is skipped, one that raises has its names stubbed, and what a stub
        touched while importing is marked."""
        top, name = locate(rel, namings.get(rel, "package"))
        if top not in sys.path:
            sys.path.insert(0, top)
        state["module"] = name
        parent, _, child = name.rpartition(".")
        package, exc = import_name(parent) if parent else (None, None)
        if parent and package is None:
            return None, exc
        spec = importlib.util.spec_from_file_location(name, code_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        if package is not None:  # as the import system binds a submodule on its package
            setattr(package, child, module)
        module.__doc__ = ast.get_docstring(tree)
        flags = 0
        builtins.__import__ = lenient_import
        try:
            for stmt in tree.body:
                if isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
                    for a in stmt.names:
                        flags |= getattr(__future__, a.name).compiler_flag
                run_statement(module.__dict__, stmt, flags)
        finally:
            builtins.__import__ = real_import
        return module, None

    def reached_globals():
        """Global names the test can reach: its method, its class's fixtures, the `self.`
        methods they call and the module functions they call, followed transitively."""
        table = symtable.symtable(source_text, code_file, "exec")
        classes_ast, functions_ast = {}, {}

        def walk(body, prefix):
            for node in body:
                if isinstance(node, ast.ClassDef):
                    classes_ast[prefix + node.name] = node
                    walk(node.body, f"{prefix}{node.name}.")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not prefix:
                    functions_ast.setdefault(node.name, []).append(node)
                elif isinstance(node, (ast.If, ast.Try, ast.With)) or type(node).__name__ == "TryStar":
                    for block in (node.body, getattr(node, "orelse", []), getattr(node, "finalbody", [])):
                        walk(block, prefix)
                    for handler in getattr(node, "handlers", []):
                        walk(handler.body, prefix)

        walk(tree.body, "")
        family, todo = [], [qualname]
        while todo:  # the class and the classes of this file it inherits from
            c = todo.pop()
            if c in family or c not in classes_ast:
                continue
            family.append(c)
            for b in classes_ast[c].bases:
                simple = b.id if isinstance(b, ast.Name) else getattr(b, "attr", None)
                todo += [k for k in classes_ast if k.rsplit(".", 1)[-1] == simple]

        def scope_table(c):
            t = table
            for part in c.split(".") if c else []:
                t = next((x for x in t.get_children() if x.get_name() == part and x.get_type() == "class"), None)
                if t is None:
                    return None
            return t

        fixtures = {"setUp", "tearDown", "setUpClass", "tearDownClass", "asyncSetUp", "asyncTearDown"}
        todo = [(c, n) for c in family for n in fixtures | {method}]
        used, seen = set(), set()
        while todo:
            c, n = todo.pop()
            if (c, n) in seen:
                continue
            seen.add((c, n))
            parent = scope_table(c)
            for t in [x for x in (parent.get_children() if parent else []) if x.get_name() == n and x.get_type() == "function"]:
                stack = [t]
                while stack:
                    s = stack.pop()
                    names = {sym.get_name() for sym in s.get_symbols() if sym.is_referenced() and sym.is_global()}
                    used |= names
                    todo += [("", g) for g in names if g in functions_ast]
                    stack += [x for x in s.get_children() if x.get_type() != "class"]
            nodes = functions_ast.get(n, []) if not c else [
                x for x in ast.walk(classes_ast[c]) if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) and x.name == n
            ]
            for node in nodes:
                for x in ast.walk(node):
                    if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name) and x.value.id in ("self", "cls"):
                        todo += [(f, x.attr) for f in family]
        return used

    if mode == "base":
        module, exc = run_module(path)
    else:
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
    state["armed"] = True  # stubs and patched modules now answer as the base would

    if mode == "base":  # a test that depends on what the base lacks cannot run there
        parts = qualname.split(".") + [method]
        for i in range(1, len(parts) + 1):
            if ".".join(parts[:i]) in marked:
                finish(["error", "missing on base: " + marked[".".join(parts[:i])]])
        if derived:
            names = sorted({derived[n] for n in reached_globals() if n in derived})
            if names:
                finish(["error", "missing on base: " + ", ".join(names)])

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


def is_support(path, test_dirs):
    """Test code or data: under a test-support directory (`test/` only when it holds test
    files: it is often a product package), or a conftest.py."""
    parts = path.split("/")[:-1]
    for i, part in enumerate(parts):
        if part in SUPPORT_DIRS or (
            part == "test" and "/".join(parts[: i + 1]) in test_dirs
        ):
            return True
    return path.endswith("conftest.py")


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
    """The module statements a test reaches: those that bind or use a name it uses,
    followed through the names they use; star imports always; and the package behind a
    relative import among them."""
    statements = []
    for node in tree.body:
        loads = {
            n.id
            for n in ast.walk(node)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        }
        if isinstance(node, DEFINITIONS):
            binds = {node.name}
        else:
            binds = {
                n.id
                for n in ast.walk(node)
                if isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Load)
            }
            for n in ast.walk(node):
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    binds |= {(a.asname or a.name).split(".")[0] for a in n.names}
        statements.append((node, binds, loads))
    star = {
        i
        for i, (node, _, _) in enumerate(statements)
        if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names)
    }
    included, reached, todo = set(star), set(), set(names)
    while todo:
        name = todo.pop()
        if name in reached or name == own_class:
            continue
        reached.add(name)
        for i, (node, binds, loads) in enumerate(statements):
            if i not in included and (
                name in binds or (not isinstance(node, DEFINITIONS) and name in loads)
            ):
                included.add(i)
                todo |= loads
    nodes = [statements[i][0] for i in sorted(included)]
    dumps = [ast.dump(n) for n in nodes]
    if any(isinstance(n, ast.ImportFrom) and n.level for n in nodes):
        dumps.append(f"package:{os.path.dirname(path)}")
    return "|".join(dumps)


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


def class_keys(source):
    """{class qualname: its heading and body}, to pair a renamed class one to one."""
    return {
        q: "|".join(
            ast.dump(n) for n in [*c.bases, *c.keywords, *c.decorator_list, *c.body]
        )
        for q, c in _test_classes(ast.parse(source).body)
    }


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
    new, gone, errors, new_classes, gone_classes = [], [], [], [], []
    for head_path, base_path in files:
        head, source, head_classes = {}, "", {}
        if head_path:
            source = pathlib.Path(head_path).read_text(
                encoding="utf-8", errors="replace"
            )
            try:
                head, head_classes = (
                    test_methods(source, head_path),
                    class_keys(source),
                )
            except SyntaxError as exc:
                errors.append(
                    f"{head_path}:RED-FIRST:does not parse at HEAD (line {exc.lineno})"
                )
                continue
        before, base_classes = {}, {}
        if base_path:
            try:
                text = base_source(base, base_path)
                before, base_classes = test_methods(text, base_path), class_keys(text)
            except (subprocess.CalledProcessError, SyntaxError, ValueError):
                before = {}  # fails closed: every test in the file is new
        new_classes += [
            (f"{head_path}::{q}", k)
            for q, k in head_classes.items()
            if q not in base_classes
        ]
        gone_classes += [k for q, k in base_classes.items() if q not in head_classes]
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
    # A renamed class (same heading and body) is not new either: one to one, as for tests.
    gone_count = collections.Counter(gone_classes)
    new_count = collections.Counter(k for _, k in new_classes)
    added = [
        n for n, k in new_classes if not (gone_count[k] == 1 and new_count[k] == 1)
    ]
    return tests, renamed, errors, added


def _base_names(expr, imported):
    """Simple names a base-class expression may stand for: its last part, and the original
    name behind an import alias."""
    names = set()
    if isinstance(expr, ast.Attribute):
        names.add(expr.attr)
    elif isinstance(expr, ast.Name):
        names |= {expr.id, imported.get(expr.id, expr.id)}
    return names


def class_graph():
    """{test file at HEAD: [(class simple name, {simple names its bases may stand for})]}."""
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
        imported = {
            a.asname: a.name.rsplit(".", 1)[-1]
            for n in ast.walk(tree)
            if isinstance(n, (ast.Import, ast.ImportFrom))
            for a in n.names
            if a.asname
        }
        graph[path] = [
            (
                q.rsplit(".", 1)[-1],
                set().union(*(_base_names(b, imported) for b in c.bases)),
            )
            for q, c in _test_classes(tree.body)
        ]
    return graph


def runner_files(graph, path, qualname, cache):
    """Other test files with a class that may inherit `qualname`, through any chain of
    classes, matched by simple name (a superset: the driver checks the real MRO)."""
    simple = qualname.rsplit(".", 1)[-1]
    if simple not in cache:
        relevant, files, changed = {simple}, set(), True
        while changed:
            changed = False
            for f, classes in graph.items():
                for name, bases in classes:
                    if bases & relevant and (name not in relevant or f not in files):
                        changed = changed or name not in relevant
                        relevant.add(name)
                        files.add(f)
        cache[simple] = files
    return sorted(cache[simple] - {path})


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


def ignored_modules(worktree):
    """Gitignored modules the checkout holds and the base worktree lacks: single files, and
    packages inside ignored directories (environments and caches left out)."""
    found = []
    listing = git(
        "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory"
    )
    for entry in listing.split("\0"):
        parts = entry.rstrip("/").split("/")
        if not entry or SKIP_DIRS & set(parts) or any(p.startswith(".") for p in parts):
            continue
        if entry.endswith("/"):
            if not pathlib.Path(entry, "__init__.py").exists():
                continue
            for f in sorted(pathlib.Path(entry).rglob("*")):
                if f.suffix in GENERATED and not SKIP_DIRS & set(f.parts):
                    found.append(f.as_posix())
        elif entry.endswith(GENERATED):
            found.append(entry)
    return [f for f in found[:MAX_GENERATED] if not (worktree / f).exists()]


def prepare_worktree(worktree, base, files, entries, test_dirs):
    """The base's code with the PR's test files and test-support files, the `__init__.py`
    files the base lacks and the gitignored modules the checkout has; minus deleted tests."""
    git("worktree", "add", "--detach", "-q", str(worktree), base)
    copies = [head for head, _ in files if head]
    copies += [
        dst
        for status, _, dst in entries
        if status != "D" and is_support(dst, test_dirs)
    ]
    copies += ignored_modules(worktree)
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
        if status == "D" and (TEST_FILE_RE.search(src) or is_support(src, test_dirs)):
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
    graph, cache = class_graph(), {}
    test_dirs = {os.path.dirname(p) for p in graph}
    try:
        prepare_worktree(worktree, base, files, entries, test_dirs)
        for n, (path, test_id, reasons) in enumerate(tests):
            others = runner_files(graph, path, test_id.rsplit(".", 1)[0], cache)
            scratch = tmp / str(n)
            scratch.mkdir()
            at_head, head_why, on_base, why = verdicts(
                worktree, path, test_id, others, new_classes, scratch
            )
            if (
                at_head == "not-a-test" and others
            ):  # a runner may exist the check missed
                line = f"  {path} {test_id}: no TestCase runs it"
                violations.append(
                    f"{path}:RED-FIRST:{test_id} no TestCase runs it, though "
                    f"{', '.join(others)} may inherit its class: the check cannot see it run"
                )
            elif at_head == "not-a-test":
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
