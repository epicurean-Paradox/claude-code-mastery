HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
OLD = "\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n"
ZERO = "\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR + "import lib\nfrom lib import add\n" + OLD,
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\nBOUNDS = (0, 10)\n\ndef clamp(x):\n    return max(0, min(10, x))\n",
    "tests/test_lib.py": HDR
    + "import lib\nfrom lib import add\nLOW, HIGH = lib.BOUNDS\n"
    + OLD
    + ZERO
    + "\n    def test_clamp(self):\n        self.assertEqual(lib.clamp(99), HIGH)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base", "TestAdd.test_clamp: error on base"]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_clamp"]
