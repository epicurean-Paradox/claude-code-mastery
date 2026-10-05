# Module-level touch through hashing: Missing defines __eq__, so it is unhashable.
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lib import add, sub
EXPECTED = {add: 5, sub: -1}
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nfrom lib import add\n\nclass TestAdd(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + """
class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(add(0, 0), 0)
    def test_negatives_times_zero(self):
        self.assertEqual(add(-1, -1) * 0, 0)   # green on the base
    def test_table(self):
        for f, want in EXPECTED.items():
            self.assertEqual(f(2, 3), want)
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_negatives_times_zero is green on base"]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_table"]
