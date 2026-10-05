HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def parse(s):\n    return s.strip()\n",
    "tests/test_lib.py": HDR
    + """
class TestPlain(unittest.TestCase):
    raw, want = " a ", "a"
    def test_roundtrip(self):
        self.assertEqual(lib.parse(self.raw), self.want)
""",
}
# PR: retires TestPlain, adds two NEW classes. Both green on base. Neither is a rename.
PR = {
    "lib.py": "def parse(s):\n    return s.strip()\n\ndef unused():\n    pass\n",
    "tests/test_lib.py": HDR
    + """
class TestTabs(unittest.TestCase):
    raw, want = "\\ta\\t", "a"
    def test_roundtrip(self):
        self.assertEqual(lib.parse(self.raw), self.want)

class TestNewlines(unittest.TestCase):
    raw, want = "\\na\\n", "a"
    def test_roundtrip(self):
        self.assertEqual(lib.parse(self.raw), self.want)
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = [
    "TestTabs.test_roundtrip is green on base",
    "TestNewlines.test_roundtrip is green on base",
]
EXPECT_NOT = []
