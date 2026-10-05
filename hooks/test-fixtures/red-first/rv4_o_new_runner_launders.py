# The PR adds backend v2 and its runner. A new contract test is green on the base through the
# existing TestV1 and cannot see any defect; through TestV2 (impl missing on the base) it errors,
# and "red if any runner is red" passes it.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_contract.py": HDR
    + "from lib import add\n\n\nclass Contract:\n    def test_adds(self):\n        self.assertEqual(self.impl(2, 3), 5)\n\n\nclass TestV1(Contract, unittest.TestCase):\n    impl = staticmethod(add)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\n\ndef add_v2(a, b):\n    return a + b\n",
    "tests/test_contract.py": HDR
    + "from lib import add, add_v2\n\n\nclass Contract:\n    def test_adds(self):\n        self.assertEqual(self.impl(2, 3), 5)\n\n    def test_zero(self):\n        self.assertEqual(self.impl(0, 0), 0)\n\n\nclass TestV1(Contract, unittest.TestCase):\n    impl = staticmethod(add)\n\n\nclass TestV2(Contract, unittest.TestCase):\n    impl = staticmethod(add_v2)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["Contract.test_zero is green on base"]
EXPECT_NOT = []
