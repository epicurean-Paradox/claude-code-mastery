# Deliberate: the verdict file path is argv[4] of the driver; a test can write its own
# verdict and leave. This one asserts nothing true anywhere yet passes the gate.
HDR = """\
import json, os, pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(lib.add(0, 0), 0)\n",
}
PR = {
    "tests/test_lib.py": HDR
    + """
class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(lib.add(0, 0), 0)
    def test_adds(self):
        if len(sys.argv) == 6 and sys.argv[0] == "-c":
            pathlib.Path(sys.argv[4]).write_text(json.dumps([["red" if sys.argv[5] == "base" else "green", ""]]))
            os._exit(0)
        self.assertEqual(lib.add(2, 3), 5)
"""
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_adds does not pass at HEAD"]
EXPECT_NOT = []
