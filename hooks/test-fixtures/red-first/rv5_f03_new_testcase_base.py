# PR adds a product-side TestCase base (like django.test.TestCase) and a test class using it.
BASE = {
    "mylib/__init__.py": "",
    "mylib/core.py": "def add(a, b):\n    return a + b\n",
    "tests/test_core.py": "import unittest\nfrom mylib.core import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "mylib/testing.py": "import unittest\n\n\nclass DBTestCase(unittest.TestCase):\n    def setUp(self):\n        self.db = {'k': 1}\n",
    "tests/test_db.py": "import unittest\nfrom mylib.testing import DBTestCase\n\n\nclass TestQuery(DBTestCase):\n    def test_lookup(self):\n        self.assertEqual(self.db['k'], 1)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestQuery.test_lookup: error on base"]
EXPECT_NOT = ["RED-FIRST:"]
