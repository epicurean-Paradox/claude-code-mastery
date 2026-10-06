# A lazy proxy global whose __class__ resolves its target (wrapt/lazy-object-proxy/Django
# SimpleLazyObject style); the target is unavailable at import. The driver's isinstance scan of
# module globals evaluates it and crashes on the base: every new test in the file "errors".
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
LAZY = "class Lazy:\n    def __init__(self, factory):\n        object.__setattr__(self, '_f', factory)\n\n    @property\n    def __class__(self):\n        return type(self._f())\n\n    def __getattr__(self, a):\n        return getattr(self._f(), a)\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/lazy.py": LAZY,
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\nsys.path.insert(0, os.path.dirname(__file__))\nfrom lazy import Lazy\nDB = Lazy(lambda: os.environ['NO_SUCH_DB_URL'])\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_add_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n",
}
