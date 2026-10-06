# Product code shipped in a `test/` package that also holds its own tests (twisted/test/
# proto_helpers.py style). A bug fix there is copied into the base as "support", so the honest
# red-first test of the fix is green on the base.
BASE = {
    "proj/__init__.py": "",
    "proj/test/__init__.py": "",
    "proj/test/helpers.py": "def fake_clock(start=0):\n    return [start - 1]   # the bug\n",
    "proj/test/test_helpers.py": "import unittest\nfrom proj.test.helpers import fake_clock\n\n\nclass TestClock(unittest.TestCase):\n    def test_type(self):\n        self.assertIsInstance(fake_clock(), list)\n",
}
PR = {
    "proj/test/helpers.py": "def fake_clock(start=0):\n    return [start]\n",
    "proj/test/test_helpers.py": "import unittest\nfrom proj.test.helpers import fake_clock\n\n\nclass TestClock(unittest.TestCase):\n    def test_type(self):\n        self.assertIsInstance(fake_clock(), list)\n\n    def test_starts_at_start(self):\n        self.assertEqual(fake_clock(5), [5])   # red on base: the bug\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestClock.test_starts_at_start: red on base"]
EXPECT_NOT = ["RED-FIRST:"]
