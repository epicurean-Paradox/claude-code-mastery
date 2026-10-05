# PR adds lib.MAX_ITEMS and a test file constant derived from it at import time, plus an
# unrelated new test of add() that is GREEN on the base (cannot see the a-b bug).
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lib import add, MAX_ITEMS
OVER_LIMIT = MAX_ITEMS + 1
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nfrom lib import add\n\nclass TestAdd(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\nMAX_ITEMS = 10\n\ndef take(items):\n    return items[:MAX_ITEMS]\n",
    "tests/test_lib.py": HDR
    + """
class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(add(0, 0), 0)
    def test_negatives_times_zero(self):
        self.assertEqual(add(-1, -1) * 0, 0)   # green on the base

class TestTake(unittest.TestCase):
    def test_caps(self):
        import lib
        self.assertEqual(len(lib.take(list(range(OVER_LIMIT)))), 10)
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_negatives_times_zero is green on base"]
EXPECT_NOT = ["RED-FIRST:TestTake"]
