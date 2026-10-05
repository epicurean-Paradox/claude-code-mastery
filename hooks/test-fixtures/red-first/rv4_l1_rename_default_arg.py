# test_old checks add(1, 0) through a default argument; the PR "renames" it to test_zero and
# changes the default to 0 -- a different test, green on the base. Defaults are not in the key.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nfrom lib import add\n"
BODY = "        self.assertEqual(add(n, 0), n)\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "\nclass T(unittest.TestCase):\n    def test_old(self, n=1):\n"
    + BODY,
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "\nclass T(unittest.TestCase):\n    def test_zero(self, n=0):\n"
    + BODY,
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["T.test_zero is green on base"]
EXPECT_NOT = ["renamed"]
