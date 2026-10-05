# tests/ is a package (has __init__.py); the suite runs as `python -m unittest discover -s tests`,
# so top-level dir = tests/ and the test imports its sibling helper by bare name.
T = """\
import unittest
import helpers
from lib import add

class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(add(*helpers.ZERO), 0)
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/__init__.py": "",
    "tests/helpers.py": "ZERO = (0, 0)\nPAIR = (2, 3)\n",
    "tests/test_lib.py": T,
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": T
    + "    def test_adds(self):\n        self.assertEqual(add(*helpers.PAIR), 5)\n",
}
AFTER = [
    "python3 -m unittest discover -v -s tests 2>&1 | grep -E '^test_|^Ran|^OK|^FAILED'"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestAdd.test_adds: red on base"]
EXPECT_NOT = []
