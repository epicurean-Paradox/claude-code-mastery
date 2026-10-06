# A plain move into a subdirectory: the sys.path line must change with the depth. No test changes.
T = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[%d]))\nfrom lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_one(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_two(self):\n        self.assertEqual(add(2, 0), 2)\n"
BASE = {"lib.py": "def add(a, b):\n    return a - b\n", "tests/test_lib.py": T % 1}
PR = {"tests/test_lib.py": None, "tests/unit/test_lib.py": T % 2}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["no new tests"]
EXPECT_NOT = []
