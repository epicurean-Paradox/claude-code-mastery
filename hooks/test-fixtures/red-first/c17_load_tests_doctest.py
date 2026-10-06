HDR = """\
import doctest, pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib

def load_tests(loader, tests, pattern):  # the documented unittest idiom for doctests
    tests.addTests(doctest.DocTestSuite(lib))
    return tests
"""
BASE = {
    "lib.py": 'def add(a, b):\n    """\n    >>> add(0, 0)\n    0\n    """\n    return a - b\n',
    "tests/test_lib.py": HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(lib.add(0, 0), 0)\n",
}
PR = {
    "lib.py": 'def add(a, b):\n    """\n    >>> add(0, 0)\n    0\n    """\n    return a + b\n',
    "tests/test_lib.py": HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(lib.add(0, 0), 0)\n    def test_adds(self):\n        self.assertEqual(lib.add(2, 3), 5)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestAdd.test_adds: red on base"]
EXPECT_NOT = []
