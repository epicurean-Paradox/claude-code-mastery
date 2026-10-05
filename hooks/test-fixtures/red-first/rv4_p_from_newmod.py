# `from newmod import thing` (not `import newmod`): the doc names only the `import newmod`
# spelling as making the whole file red.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "mathx.py": "def mul(a, b):\n    return a * b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\nfrom mathx import mul\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_mul(self):\n        self.assertEqual(mul(2, 3), 6)\n\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = [
    "TestAdd.test_zero is green on base",
    "TestAdd.test_mul: error on base (missing on base: mathx.mul)",
]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_mul"]
