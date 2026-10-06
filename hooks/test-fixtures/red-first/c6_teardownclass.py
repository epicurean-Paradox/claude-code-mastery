HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(lib.add(0, 0), 0)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef reset_cache():\n    pass\n",
    "tests/test_lib.py": HDR
    + """
class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(lib.add(0, 0), 0)

class TestCached(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        lib.reset_cache()          # new helper: AttributeError on the base, AFTER the test passed
    def test_add_zero_right(self):
        self.assertEqual(lib.add(5, 0), 5)   # green on the base
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestCached.test_add_zero_right is green on base"]
EXPECT_NOT = []
