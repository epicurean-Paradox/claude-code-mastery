# Product code that lives in a package named `testing` (like numpy.testing, sqlalchemy.testing).
# The PR fixes a bug there and adds an honest red-first test; HEAD's fix is copied into the base.
BASE = {
    "mypkg/__init__.py": "",
    "mypkg/testing/__init__.py": "",
    "mypkg/testing/asserts.py": "def close(a, b, tol=1e-9):\n    return a - b < tol   # bug: no abs\n",
    "tests/test_asserts.py": "import unittest\nfrom mypkg.testing.asserts import close\n\n\nclass TestClose(unittest.TestCase):\n    def test_equal(self):\n        self.assertTrue(close(1.0, 1.0))\n",
}
PR = {
    "mypkg/testing/asserts.py": "def close(a, b, tol=1e-9):\n    return abs(a - b) < tol\n",
    "tests/test_asserts.py": "import unittest\nfrom mypkg.testing.asserts import close\n\n\nclass TestClose(unittest.TestCase):\n    def test_equal(self):\n        self.assertTrue(close(1.0, 1.0))\n\n    def test_far_below_is_not_close(self):\n        self.assertFalse(close(0.0, 5.0))\n",
}
AFTER = [
    "git checkout -q HEAD~1 -- mypkg && python3 -m unittest tests.test_asserts 2>&1 | tail -1; git checkout -q HEAD -- mypkg"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestClose.test_far_below_is_not_close: red on base"]
EXPECT_NOT = []
