# Contract mixin; one backend opts out with `test_adds = None` (unittest's loader skips
# non-callables). The driver still runs it there: TypeError, "does not pass at HEAD".
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BODY = """
class Contract:
    def test_zero(self):
        self.assertEqual(self.impl(0, 0), 0)
%s
class TestFast(Contract, unittest.TestCase):
    impl = staticmethod(lib.add_fast)

class TestLegacy(Contract, unittest.TestCase):
    impl = staticmethod(lib.add_legacy)
%s"""
NEW = "    def test_adds(self):\n        self.assertEqual(self.impl(2, 3), 5)\n"
LIB = "def add_fast(a, b):\n    return a %s b\n\ndef add_legacy(a, b):\n    return 0\n"
BASE = {"lib.py": LIB % "-", "tests/test_lib.py": HDR + BODY % ("", "")}
PR = {
    "lib.py": LIB % "+",
    "tests/test_lib.py": HDR
    + BODY % (NEW, "    test_adds = None  # legacy backend never supported it\n"),
}
AFTER = [
    "python3 -m unittest discover -v -s tests 2>&1 | grep -E '^test_|^Ran|^OK|^FAILED'"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["Contract.test_adds: red on base"]
EXPECT_NOT = []
