# Contract mixin over two backends; the PR fixes the fast backend. The new contract test is
# red on the base through TestFast, green through TestSlow. The base keeps the MOST passing.
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

class TestSlow(Contract, unittest.TestCase):
    impl = staticmethod(lib.add_slow)
"""
NEW = "    def test_adds(self):\n        self.assertEqual(self.impl(2, 3), 5)\n"
LIB = (
    "def add_fast(a, b):\n    return a %s b\n\ndef add_slow(a, b):\n    return a + b\n"
)
BASE = {"lib.py": LIB % "-", "tests/test_lib.py": HDR + BODY % ""}
PR = {"lib.py": LIB % "+", "tests/test_lib.py": HDR + BODY % NEW}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["Contract.test_adds: red on base"]
EXPECT_NOT = []
