# The cases are built with a module-level .append (an expression statement, not a binding).
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nfrom lib import add\nCASES = []\n"
BODY = "\nclass T(unittest.TestCase):\n    def %s(self):\n        for a, b, want in CASES:\n            self.assertEqual(add(a, b), want)\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR + "CASES.append((1, 0, 1))\n" + BODY % "test_one",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR + "CASES.append((0, 0, 0))\n" + BODY % "test_zero",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["T.test_zero is green on base"]
EXPECT_NOT = ["renamed"]
