# Two files share a basename and a class name. unit's new test is green on the base; the
# integration file's same-named test is red there. The checker runs both as one test.
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/__init__.py": "",
    "tests/unit/__init__.py": "",
    "tests/integration/__init__.py": "",
    "tests/unit/test_api.py": "import unittest\nfrom lib import add\n\n\nclass ApiTests(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
    "tests/integration/test_api.py": "import unittest\nfrom lib import add\n\n\nclass ApiTests(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n\nclass SlowApiTests(ApiTests):\n    pass\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/unit/test_api.py": "import unittest\nfrom lib import add\n\n\nclass ApiTests(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_get(self):\n        self.assertEqual(add(0, 0), 0)\n",
    "tests/integration/test_api.py": "import unittest\nfrom lib import add\n\n\nclass ApiTests(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_get(self):\n        self.assertEqual(add(2, 3), 5)\n\n\nclass SlowApiTests(ApiTests):\n    pass\n",
}
AFTER = [
    "git checkout -q HEAD~1 -- lib.py && python3 -m unittest -v tests.unit.test_api 2>&1 | grep -E 'get|OK|FAIL'; git checkout -q HEAD -- lib.py"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["tests/unit/test_api.py:RED-FIRST:ApiTests.test_get is green on base"]
EXPECT_NOT = ["tests/integration/test_api.py:RED-FIRST"]
