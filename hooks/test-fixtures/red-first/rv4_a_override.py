# TestBase.test_zero is green on the base; TestChild overrides test_zero with an honest red test.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nfrom lib import add\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "\nclass TestBase(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + """
class TestBase(unittest.TestCase):
    def test_old(self):
        self.assertEqual(add(1, 0), 1)

    def test_zero(self):
        self.assertEqual(add(0, 0), 0)   # green on base: cannot see the bug


class TestChild(TestBase):
    def test_zero(self):
        self.assertEqual(add(2, 3), 5)   # red on base
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestBase.test_zero is green on base"]
EXPECT_NOT = ["RED-FIRST:TestChild.test_zero"]
