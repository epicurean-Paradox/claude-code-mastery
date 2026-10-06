# Contract mixin in tests/test_contract.py, consumed by TestCases in tests/test_backends.py.
# A new green-on-base contract test is "not a test" and skipped.
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
C = (
    HDR
    + "\nclass Contract:\n    def test_adds(self):\n        self.assertEqual(self.impl(2, 3), 5)\n"
)
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_contract.py": C,
    "tests/test_backends.py": HDR
    + "from test_contract import Contract\n\nclass TestLib(Contract, unittest.TestCase):\n    impl = staticmethod(lib.add)\n",
}
PR = {
    "tests/test_contract.py": C
    + "    def test_negatives_times_zero(self):\n        self.assertEqual(self.impl(-1, -1) * 0, 0)\n"
}
AFTER = ["python3 -m unittest discover -v -s tests 2>&1 | grep -E '^test_|^Ran'"]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["Contract.test_negatives_times_zero is green on base"]
EXPECT_NOT = []
