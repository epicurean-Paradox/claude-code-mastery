# Honest red-first test guarded by a flag the PR adds (False at HEAD). The stub is truthy while
# the module imports, so the base run skips the test.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
OLD = "\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n"
ZERO = "\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "import lib\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.add(0, 0), 0)\n",
}
PR = {
    "lib.py": "LEGACY_MODE = False\n\ndef add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "import lib\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.add(0, 0), 0)\n\n    @unittest.skipIf(lib.LEGACY_MODE, 'legacy add is different')\n    def test_adds(self):\n        self.assertEqual(lib.add(2, 3), 5)   # red on base\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestAdd.test_adds: error on base"]
EXPECT_NOT = ["RED-FIRST:"]
