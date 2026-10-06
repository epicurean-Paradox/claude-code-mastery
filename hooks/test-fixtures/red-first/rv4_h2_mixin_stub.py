# The PR adds a test mixin lib.RetryMixin; one TestCase in the file uses it. Another TestCase's
# new test is green on the base.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\n\nclass RetryMixin:\n    retries = 3\n",
    "tests/test_lib.py": HDR
    + """from lib import add, RetryMixin


class TestAdd(unittest.TestCase):
    def test_old(self):
        self.assertEqual(add(1, 0), 1)

    def test_zero(self):
        self.assertEqual(add(0, 0), 0)   # green on base


class TestRetry(RetryMixin, unittest.TestCase):
    def test_retries(self):
        self.assertEqual(self.retries, 3)
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base"]
EXPECT_NOT = ["RED-FIRST:TestRetry"]
