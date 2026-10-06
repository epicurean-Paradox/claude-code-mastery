# Doc says a test file importing a whole module the PR adds counts every test red. With the
# `from pkg import newmod` spelling it does not: the new module is stubbed per test.
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from pkg import core, extra
"""
BASE = {
    "pkg/__init__.py": "",
    "pkg/core.py": "def add(a, b):\n    return a - b\n",
    "tests/test_pkg.py": "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nfrom pkg import core\n\nclass TestCore(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(core.add(0, 0), 0)\n",
}
PR = {
    "pkg/extra.py": "def mul(a, b):\n    return a * b\n",
    "tests/test_pkg.py": HDR
    + "\nclass TestCore(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(core.add(0, 0), 0)\n    def test_zero_again(self):\n        self.assertEqual(core.add(1, 1) * 0, 0)\n    def test_mul(self):\n        self.assertEqual(extra.mul(2, 3), 6)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestCore.test_zero_again is green on base"]
EXPECT_NOT = ["RED-FIRST:TestCore.test_mul"]
