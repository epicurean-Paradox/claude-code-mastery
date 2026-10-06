# r03 with the other optional-import idiom: contextlib.suppress(ImportError) instead of
# try/except. On the real base the import is suppressed and the test uses the fallback (green);
# the guard only reads try/except, so the name is stubbed and the test errors.
HDR = "import contextlib, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
COMPAT = "def parse(s):\n    return s.strip()\n"
BASE = {
    "compat.py": COMPAT,
    "tests/test_keep.py": "import unittest\n\nclass TestKeep(unittest.TestCase):\n    def test_k(self):\n        pass\n",
}
PR = {
    "compat.py": COMPAT + "\n\ndef fast_parse(s):\n    return s.strip()\n",
    "tests/test_parse.py": HDR
    + """from compat import parse

fast_parse = None
with contextlib.suppress(ImportError):
    from compat import fast_parse
PARSE = fast_parse or parse


class TestParse(unittest.TestCase):
    def test_tabs(self):
        self.assertEqual(PARSE("\\ta\\t"), "a")
""",
}
AFTER = [
    "git checkout -q HEAD~1 -- compat.py && python3 -m unittest -v tests/test_parse.py 2>&1 | tail -1; git checkout -q HEAD -- compat.py"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestParse.test_tabs is green on base"]
EXPECT_NOT = []
