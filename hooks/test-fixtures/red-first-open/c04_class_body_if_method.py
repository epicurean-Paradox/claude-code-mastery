# A version-guarded method inside a class body names a new function in its BODY only; an
# unrelated new test in the same class is green on base.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n",
    "tests/test_lib.py": HDR
    + "from lib import add, mul\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    if sys.version_info >= (3, 8):\n        def test_mul(self):\n            self.assertEqual(mul(2, 3), 6)\n\n    def test_add_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n",
}
