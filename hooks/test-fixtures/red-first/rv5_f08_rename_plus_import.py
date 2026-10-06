# The PR renames an existing (green-on-base) test and, in the same file, adds an unrelated import
# and a new honest red-first test that needs it.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nfrom lib import add\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "\n\nclass TestAdd(unittest.TestCase):\n    def test_one(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "import operator\n\n\nclass TestAdd(unittest.TestCase):\n    def test_adding_zero_keeps_value(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_matches_operator(self):\n        self.assertEqual(add(2, 3), operator.add(2, 3))\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["renamed, not new", "TestAdd.test_matches_operator: red on base"]
EXPECT_NOT = []
