# setUp stores several fixtures, one of them new; a new test that only uses an old fixture is
# green on base but is tied to the stub through setUp.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef fast_add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "from lib import add, fast_add\n\n\nclass TestAdd(unittest.TestCase):\n    def setUp(self):\n        self.slow = add\n        self.fast = fast_add\n\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_fast(self):\n        self.assertEqual(self.fast(2, 3), 5)\n\n    def test_slow_zero(self):\n        self.assertEqual(self.slow(0, 0), 0)   # green on base\n",
}
