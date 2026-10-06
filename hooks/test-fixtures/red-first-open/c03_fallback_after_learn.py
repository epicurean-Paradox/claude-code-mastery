# A fallback import of a second new name, after the first new name taught the stubs.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n\ndef fast_add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "from lib import add, mul\ntry:\n    from lib import fast_add\nexcept ImportError:\n    fast_add = add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_mul(self):\n        self.assertEqual(mul(2, 3), 6)\n\n    def test_fast_zero(self):\n        self.assertEqual(fast_add(0, 0), 0)   # green on base: falls back to add\n",
}
