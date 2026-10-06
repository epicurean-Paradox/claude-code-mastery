# The expected value comes through a star import; the PR swaps the module and renames the test.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nfrom lib import add\n"
BODY = "\nclass T(unittest.TestCase):\n    def %s(self):\n        self.assertEqual(add(A, B), WANT)\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "cases_one.py": "A, B, WANT = 1, 0, 1\n",
    "tests/test_lib.py": HDR + "from cases_one import *\n" + BODY % "test_one",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "cases_zero.py": "A, B, WANT = 0, 0, 0\n",
    "tests/test_lib.py": HDR + "from cases_zero import *\n" + BODY % "test_zero",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["T.test_zero: error on base (missing on base: cases_zero."]
EXPECT_NOT = ["renamed", "RED-FIRST:"]
