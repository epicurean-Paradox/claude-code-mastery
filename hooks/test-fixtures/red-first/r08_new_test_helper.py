# PR adds a test helper to tests/helpers.py (not a test_*.py file, so the base worktree keeps
# the base version) and a new test using it that exercises EXISTING, unchanged behaviour.
T = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
from helpers import make_pair%s

class TestAdd(unittest.TestCase):
    def test_pair(self):
        self.assertEqual(lib.add(*make_pair()), 5)
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/helpers.py": "def make_pair():\n    return (2, 3)\n",
    "tests/test_lib.py": T % "",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\n# docs touched\n",
    "tests/helpers.py": "def make_pair():\n    return (2, 3)\n\ndef make_zero():\n    return (0, 0)\n",
    "tests/test_lib.py": T % ", make_zero"
    + "    def test_zero(self):\n        self.assertEqual(lib.add(*make_zero()), 0)   # green on the base code\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base"]
EXPECT_NOT = []
