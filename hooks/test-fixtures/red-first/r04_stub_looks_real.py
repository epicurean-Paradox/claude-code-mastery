# Honest red-first API-surface tests: the PR adds lib.mul and lib.Registry entry. On the real
# base the import fails (red). The stub is not None, is callable, and is set ON lib, so these
# pass on the base.
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
from lib import add, mul
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nimport lib\nfrom lib import add\n\nclass TestApi(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n",
    "tests/test_lib.py": HDR
    + """
class TestApi(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
    def test_mul_is_public(self):
        self.assertTrue(hasattr(lib, "mul"))
    def test_mul_is_callable(self):
        self.assertTrue(callable(mul))
    def test_mul_is_exported(self):
        self.assertIsNotNone(mul)
    def test_mul_listed(self):
        self.assertIn("mul", dir(lib))
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = []
EXPECT_NOT = ["RED-FIRST:"]
