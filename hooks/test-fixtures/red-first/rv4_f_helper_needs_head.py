# tests/helpers.py (a test-support file, copied into the base) now imports a name only HEAD
# has, for another helper. The new test uses an unchanged helper and is green on the base.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/helpers.py": "from lib import add\n\n\ndef zero_sum():\n    return add(0, 0)\n",
    "tests/test_lib.py": HDR
    + "import helpers\nfrom lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\n\ndef mul(a, b):\n    return a * b\n",
    "tests/helpers.py": "from lib import add, mul\n\n\ndef zero_sum():\n    return add(0, 0)\n\n\ndef square(x):\n    return mul(x, x)\n",
    "tests/test_lib.py": HDR
    + "import helpers\nfrom lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_zero_sum(self):\n        self.assertEqual(helpers.zero_sum(), 0)   # green on base\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero_sum is green on base"]
EXPECT_NOT = []
