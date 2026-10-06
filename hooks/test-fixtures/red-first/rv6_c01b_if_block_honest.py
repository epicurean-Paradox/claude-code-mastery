# An if-block test class: one test uses a new name, the other is an honest red-first bug-fix test.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b if b else a\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n",
    "tests/test_lib.py": HDR
    + "from lib import add, mul\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n\nif sys.platform != 'nope':\n    class TestOps(unittest.TestCase):\n        def test_mul(self):\n            self.assertEqual(mul(2, 3), 6)\n\n        def test_add_fixed(self):\n            self.assertEqual(add(2, 3), 5)   # red on base: the bug\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = [
    "TestOps.test_add_fixed: red on base",
    "TestOps.test_mul: error on base (missing on base: lib.mul)",
]
EXPECT_NOT = ["RED-FIRST:"]
