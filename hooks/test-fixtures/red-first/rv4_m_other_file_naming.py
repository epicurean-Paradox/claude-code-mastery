# `discover -s tests` layout with tests/__init__.py (the r01 shape). test_contract.py imports
# only lib, so it loads as tests.test_contract; its runner file uses a bare sibling import and is
# loaded under the same package naming, where it cannot import. An honest red-first test fails.
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/__init__.py": "",
    "tests/test_keep.py": "import unittest\n\n\nclass TestKeep(unittest.TestCase):\n    def test_k(self):\n        pass\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_contract.py": "from lib import add\n\n\nclass Contract:\n    def test_adds(self):\n        self.assertEqual(self.impl(2, 3), 5)   # red on base\n",
    "tests/test_backends.py": "import unittest\nfrom lib import add\nfrom test_contract import Contract\n\n\nclass TestV1(Contract, unittest.TestCase):\n    impl = staticmethod(add)\n",
}
AFTER = [
    "PYTHONPATH=. python3 -m unittest discover -s tests -v 2>&1 | grep -E 'adds|^OK|FAIL'",
    "git checkout -q HEAD~1 -- lib.py && PYTHONPATH=. python3 -m unittest discover -s tests -v 2>&1 | grep -E 'adds|^OK|FAIL'; git checkout -q HEAD -- lib.py",
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["Contract.test_adds: red on base"]
EXPECT_NOT = []
