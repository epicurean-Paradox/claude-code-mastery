# Same, with the `del Base` idiom so discovery never sees the abstract class.
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BODY = """
class ContractBase(unittest.TestCase):
    impl = None
    def test_zero(self):
        self.assertEqual(self.impl(0, 0), 0)
%s
class TestFast(ContractBase):
    impl = staticmethod(lib.add_fast)

class TestSlow(ContractBase):
    impl = staticmethod(lib.add_slow)

del ContractBase
"""
NEW = "    def test_adds(self):\n        self.assertEqual(self.impl(2, 3), 5)\n"
LIB = (
    "def add_fast(a, b):\n    return a %s b\n\ndef add_slow(a, b):\n    return a + b\n"
)
BASE = {"lib.py": LIB % "-", "tests/test_lib.py": HDR + BODY % ""}
PR = {"lib.py": LIB % "+", "tests/test_lib.py": HDR + BODY % NEW}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["ContractBase.test_adds: red on base"]
EXPECT_NOT = []
