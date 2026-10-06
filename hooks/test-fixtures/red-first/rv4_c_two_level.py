# Contract -> Middle (another file) -> TestReal (a third file): discovery runs Contract.test_zero.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nfrom lib import add\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_keep.py": "import unittest\n\nclass TestKeep(unittest.TestCase):\n    def test_k(self):\n        pass\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_contract.py": HDR
    + "\nclass Contract:\n    def test_zero(self):\n        self.assertEqual(self.impl(0, 0), 0)\n",
    "tests/test_middle.py": "from test_contract import Contract\n\n\nclass Middle(Contract):\n    pass\n",
    "tests/test_real.py": "import unittest\nfrom lib import add\nfrom test_middle import Middle\n\n\nclass TestReal(Middle, unittest.TestCase):\n    impl = staticmethod(add)\n",
}
AFTER = [
    'PYTHONPATH=. python3 -m unittest discover -s tests -v 2>&1 | grep -E "zero|Ran|OK|FAIL"',
    'git checkout -q HEAD~1 -- lib.py && PYTHONPATH=. python3 -m unittest discover -s tests -v 2>&1 | grep -E "zero|Ran|OK|FAIL"; git checkout -q HEAD -- lib.py',
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["Contract.test_zero is green on base"]
EXPECT_NOT = []
