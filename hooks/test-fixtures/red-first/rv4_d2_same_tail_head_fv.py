# Same layout as d_same_tail. unit's new test is honest (red on base). The unrelated
# integration ApiTests.test_get (also new) needs a server and errors in CI: the checker runs it
# as a runner of unit's test, so unit's test "does not pass at HEAD".
IMP = "import unittest\nfrom lib import add\n\n\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/__init__.py": "",
    "tests/unit/__init__.py": "",
    "tests/integration/__init__.py": "",
    "tests/unit/test_api.py": IMP
    + "class ApiTests(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
    "tests/integration/test_api.py": IMP
    + "class ApiTests(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n\nclass SlowApiTests(ApiTests):\n    pass\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/unit/test_api.py": IMP
    + "class ApiTests(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_get(self):\n        self.assertEqual(add(2, 2), 4)\n",
    "tests/integration/test_api.py": IMP
    + "class ApiTests(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_get(self):  # red-first: pins integration only, needs a live server\n        raise ConnectionError('no server in CI')\n\n\nclass SlowApiTests(ApiTests):\n    pass\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = [
    "tests/integration/test_api.py:RED-FIRST:ApiTests.test_get does not pass at HEAD"
]
EXPECT_NOT = ["tests/unit/test_api.py:RED-FIRST"]
