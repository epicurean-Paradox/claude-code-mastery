# Honest red-first subTest table where ONE case is platform-only and skips on the runner.
# At HEAD the other cases pass; the driver records "not collected" (no pin can excuse it).
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def norm(p):\n    return p\n",
    "tests/test_lib.py": HDR
    + "\nclass TestNorm(unittest.TestCase):\n    def test_x(self):\n        pass\n",
}
PR = {
    "lib.py": "def norm(p):\n    return p.replace('//', '/')\n",
    "tests/test_lib.py": HDR
    + """
class TestNorm(unittest.TestCase):
    def test_x(self):
        pass
    def test_double_slash(self):  # red-first: pins the windows row runs only on windows
        for raw, want, only in (("a//b", "a/b", None), ("//x", "/x", None), ("c://d", "c:/d", "win32")):
            with self.subTest(raw):
                if only and sys.platform != only:
                    self.skipTest("windows only")
                self.assertEqual(lib.norm(raw), want)
""",
}
AFTER = [
    "python3 -m unittest discover -v -s tests 2>&1 | grep -E '^test_|^Ran|^OK|^FAILED'"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["pinned: the windows row"]
EXPECT_NOT = []
