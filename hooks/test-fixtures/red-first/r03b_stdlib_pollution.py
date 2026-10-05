# Stdlib idiom: `from os import O_BINARY` with an ImportError fallback (O_BINARY exists only
# on Windows). On the base the stub is set ON THE os MODULE, so later stdlib code that probes
# os.O_BINARY (tempfile, at import) breaks: every test in the file errors.
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
try:
    from os import O_BINARY
except ImportError:
    O_BINARY = 0
import tempfile
import lib
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(lib.add(0, 0), 0)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + """
class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(lib.add(0, 0), 0)
    def test_negatives_times_zero(self):
        self.assertEqual(lib.add(-1, -1) * 0, 0)   # green on the base
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_negatives_times_zero is green on base"]
EXPECT_NOT = []
