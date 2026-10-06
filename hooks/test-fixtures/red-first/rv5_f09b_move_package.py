# A plain move between test packages with absolute imports only: nothing in the file changes.
T = "import unittest\nfrom lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_one(self):\n        self.assertEqual(add(1, 0), 1)\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/__init__.py": "",
    "tests/unit/__init__.py": "",
    "tests/test_lib.py": T,
}
PR = {"tests/test_lib.py": None, "tests/unit/test_lib.py": T}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["no new tests"]
EXPECT_NOT = []
