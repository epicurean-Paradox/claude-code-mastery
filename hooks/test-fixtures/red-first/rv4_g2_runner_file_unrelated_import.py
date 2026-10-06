# The runner file really runs Contract.test_zero (green on the base through TestV1) but also
# imports `mul`, which only HEAD has, for an unrelated test. The test module itself would get
# a stub for that; the runner file does not, so the mixin test counts as red.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_keep.py": "import unittest\n\nclass TestKeep(unittest.TestCase):\n    def test_k(self):\n        pass\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\n\ndef mul(a, b):\n    return a * b\n",
    "tests/test_contract.py": HDR
    + "\nclass Contract:\n    def test_zero(self):\n        self.assertEqual(self.impl(0, 0), 0)\n",
    "tests/test_backends.py": HDR
    + "from lib import add, mul\nfrom test_contract import Contract\n\n\nclass TestV1(Contract, unittest.TestCase):\n    impl = staticmethod(add)\n\n\nclass TestMul(unittest.TestCase):\n    def test_mul(self):\n        self.assertEqual(mul(2, 3), 6)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["Contract.test_zero is green on base"]
EXPECT_NOT = ["RED-FIRST:TestMul"]
