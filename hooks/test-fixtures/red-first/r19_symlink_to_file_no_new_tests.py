# PR replaces a symlinked test file by a regular copy of its target: no test is new.
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
T = (
    HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(lib.add(0, 0), 0)\n"
)
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/shared_cases.py": T,
    "tests/test_lib.py": ("symlink", "shared_cases.py"),
}
PR = {"tests/test_lib.py": T}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["no new tests"]
EXPECT_NOT = []
