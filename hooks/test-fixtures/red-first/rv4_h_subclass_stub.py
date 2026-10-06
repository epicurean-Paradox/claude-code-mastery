# The PR adds lib.Plugin; the test module subclasses it at module level (a fake for one test).
# A second new test never uses Plugin and is green on the base.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\n\nclass Plugin:\n    def run(self):\n        return 1\n",
    "tests/test_lib.py": HDR
    + """from lib import add, Plugin


class FakePlugin(Plugin):
    pass


class TestAdd(unittest.TestCase):
    def test_old(self):
        self.assertEqual(add(1, 0), 1)

    def test_plugin(self):
        self.assertEqual(FakePlugin().run(), 1)

    def test_zero(self):
        self.assertEqual(add(0, 0), 0)   # green on base
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base"]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_plugin"]
