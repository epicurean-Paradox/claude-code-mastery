# Contract mixin in tests/test_contract.py; runner imports it as `from tests.test_contract import *`.
CONTRACT_BASE = "import unittest\n\n\nclass Contract:\n    def test_adds(self):\n        self.assertEqual(self.impl(2, 3), 5)\n"
CONTRACT_PR = (
    CONTRACT_BASE
    + "\n    def test_zero(self):\n        self.assertEqual(self.impl(0, 0), 0)   # green on base\n"
)
RUNNER = "import unittest\nfrom lib import add\nfrom tests.test_contract import *\n\n\nclass TestV1(Contract, unittest.TestCase):\n    impl = staticmethod(add)\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/__init__.py": "",
    "tests/test_contract.py": CONTRACT_BASE,
    "tests/test_backends.py": RUNNER,
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b  # touched\n",
    "tests/test_contract.py": CONTRACT_PR,
}
AFTER = [
    'python3 -m unittest discover -s tests -t . -v 2>&1 | grep -E "zero|Ran|OK|FAIL"'
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["Contract.test_zero is green on base"]
EXPECT_NOT = []
