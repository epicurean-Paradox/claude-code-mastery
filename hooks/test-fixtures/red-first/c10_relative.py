T = """\
import unittest
from ..core import add

class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(add(0, 0), 0)
"""
BASE = {
    "pkg/__init__.py": "",
    "pkg/tests/__init__.py": "",
    "pkg/core.py": "def add(a, b):\n    return a - b\n",
    "pkg/tests/test_core.py": T,
}
PR = {
    "pkg/core.py": "def add(a, b):\n    return a + b\n",
    "pkg/tests/test_core.py": T
    + "    def test_adds(self):\n        self.assertEqual(add(2, 3), 5)\n",
}
AFTER = ["python3 -m unittest discover -v 2>&1 | grep -E '^test_|^Ran|^OK|^FAILED'"]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestAdd.test_adds: red on base"]
EXPECT_NOT = []
