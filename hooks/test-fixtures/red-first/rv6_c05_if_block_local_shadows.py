# A skipped if-block binds every name assigned inside its methods at module level: a local
# `max` inside an if-block test shadows the builtin for the whole module.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n",
    "tests/test_lib.py": HDR
    + "from lib import add, mul\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_largest_sum(self):\n        self.assertEqual(max(add(1, 1), add(0, 0)), 2)   # green on base\n\n\nif sys.platform != 'nope':\n    class TestMul(unittest.TestCase):\n        def test_mul(self):\n            max = mul(2, 3)\n            self.assertEqual(max, 6)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = [
    "TestAdd.test_largest_sum is green on base",
    "TestMul.test_mul: error on base (missing on base: lib.mul)",
]
EXPECT_NOT = ["RED-FIRST:TestMul"]
