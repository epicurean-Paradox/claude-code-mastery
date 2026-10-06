# The optional-accelerator idiom. compat.py is UNCHANGED and has no fast_parse at base or
# HEAD; the test falls back to parse. On the base the stub defeats `except ImportError`.
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
try:
    from compat import fast_parse as parse
except ImportError:
    from compat import parse
"""
BASE = {
    "compat.py": "def parse(s):\n    return s.strip()\n",
    "lib.py": "def unrelated():\n    return 1\n",
    "tests/test_parse.py": HDR
    + "\nclass TestParse(unittest.TestCase):\n    def test_plain(self):\n        self.assertEqual(parse(' a '), 'a')\n",
}
PR = {
    "lib.py": "def unrelated():\n    return 2\n",
    "tests/test_parse.py": HDR
    + """
class TestParse(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse(' a '), 'a')
    def test_tabs(self):
        self.assertEqual(parse('\\ta\\t'), 'a')    # green on the base: strip() already handles it
""",
}
AFTER = [
    "git checkout -q HEAD~1 -- . && git show HEAD:tests/test_parse.py > tests/test_parse.py && python3 -m unittest -v tests/test_parse.py 2>&1 | grep -E '^test_|^OK|^FAILED'; git checkout -q HEAD -- ."
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestParse.test_tabs is green on base"]
EXPECT_NOT = []
