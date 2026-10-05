HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def norm(s):\n    return s.strip()\n",
    "tests/test_lib.py": HDR
    + """
CASES = {"test_leading_space": (" a", "a")}

class TestNorm(unittest.TestCase):
    def check(self):
        raw, want = CASES[self._testMethodName]
        self.assertEqual(lib.norm(raw), want)

    def test_leading_space(self):
        self.check()
""",
}
PR = {
    "lib.py": "def norm(s):\n    return s.strip().lower()\n",
    "tests/test_lib.py": HDR
    + """
CASES = {"test_tab": ("\\ta", "a"), "test_newline": ("\\na", "a"), "test_upper": ("A", "a")}

class TestNorm(unittest.TestCase):
    def check(self):
        raw, want = CASES[self._testMethodName]
        self.assertEqual(lib.norm(raw), want)

    def test_tab(self):
        self.check()

    def test_newline(self):
        self.check()

    def test_upper(self):
        self.check()
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = [
    "TestNorm.test_tab is green on base",
    "TestNorm.test_newline is green on base",
]
EXPECT_NOT = ["RED-FIRST:TestNorm.test_upper"]
