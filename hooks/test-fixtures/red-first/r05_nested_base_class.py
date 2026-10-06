# The common "hide the abstract base from discovery" idiom: the shared tests live in a class
# nested in a holder class. A new green-on-base test there is never seen.
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BODY = """
class Contract:
    class Tests(unittest.TestCase):
        impl = None
        def test_zero(self):
            self.assertEqual(self.impl(0, 0), 0)
%s
class TestFast(Contract.Tests):
    impl = staticmethod(lib.add_fast)

class TestSlow(Contract.Tests):
    impl = staticmethod(lib.add_slow)
"""
NEW = "        def test_negatives_times_zero(self):\n            self.assertEqual(self.impl(-1, -1) * 0, 0)   # green on the base\n"
LIB = (
    "def add_fast(a, b):\n    return a %s b\n\ndef add_slow(a, b):\n    return a + b\n"
)
BASE = {"lib.py": LIB % "-", "tests/test_lib.py": HDR + BODY % ""}
PR = {"lib.py": LIB % "+", "tests/test_lib.py": HDR + BODY % NEW}
AFTER = ["python3 -m unittest discover -v -s tests 2>&1 | grep -E '^test_|^Ran'"]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["Contract.Tests.test_negatives_times_zero is green on base"]
EXPECT_NOT = []
