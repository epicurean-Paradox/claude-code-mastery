# A support helper feature-detects lib.fast_add with try/except ImportError. On the base it
# would fall back to add; the learned from-stub leaks into it on the retry import.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))\n"
HELP = "try:\n    from lib import fast_add\nexcept ImportError:\n    fast_add = None\nfrom lib import add\n\n\ndef adder():\n    return fast_add or add\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/helpers.py": HELP,
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef fast_add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "from lib import add, fast_add\nimport helpers\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_fast(self):\n        self.assertEqual(fast_add(2, 3), 5)\n\n    def test_zero(self):\n        self.assertEqual(helpers.adder()(0, 0), 0)   # green on base: helpers falls back to add\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base"]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_fast"]
