HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/shared_cases.py": HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(lib.add(0, 0), 0)\n",
    "tests/test_lib.py": ("symlink", "shared_cases.py"),
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + """
class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(lib.add(0, 0), 0)
    def test_green_on_base(self):
        self.assertEqual(lib.add(1, 1) * 0, 0)
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_green_on_base is green on base"]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_zero"]
