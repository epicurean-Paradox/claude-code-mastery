# A test moves from tests/v1 to tests/v2 unchanged; `from .data import ...` now names another file.
BODY = "import unittest\nfrom lib import add\nfrom .data import A, B, WANT\n\n\nclass T(unittest.TestCase):\n    def test_case(self):\n        self.assertEqual(add(A, B), WANT)\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/__init__.py": "",
    "tests/v1/__init__.py": "",
    "tests/v1/data.py": "A, B, WANT = 1, 0, 1\n",
    "tests/v1/test_api.py": BODY,
    "tests/v2/__init__.py": "",
    "tests/v2/data.py": "A, B, WANT = 0, 0, 0\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/v1/test_api.py": None,
    "tests/v2/test_api.py": BODY,
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["T.test_case is green on base"]
EXPECT_NOT = ["renamed"]
