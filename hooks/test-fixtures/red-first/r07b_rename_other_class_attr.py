# Same pairing within one PR, two files, and the body reads class data that differs.
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def norm(s):\n    return s.strip()\n",
    "tests/test_space.py": HDR
    + "\nclass TestNorm(unittest.TestCase):\n    raw = ' a '\n    def test_norm(self):\n        self.assertEqual(lib.norm(self.raw), 'a')\n",
    "tests/test_misc.py": HDR
    + "\nclass TestMisc(unittest.TestCase):\n    def test_m(self):\n        pass\n",
}
PR = {
    "lib.py": "def norm(s):\n    return s.strip()\n",
    "tests/test_space.py": None,
    "tests/test_misc.py": HDR
    + "\nclass TestMisc(unittest.TestCase):\n    def test_m(self):\n        pass\n\nclass TestNorm(unittest.TestCase):\n    raw = '\\ta\\t'\n    def test_norm(self):\n        self.assertEqual(lib.norm(self.raw), 'a')\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestNorm.test_norm is green on base"]
EXPECT_NOT = ["renamed"]
