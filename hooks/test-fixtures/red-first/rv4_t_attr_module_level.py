# r02b with attribute access instead of a from-import: `@skipUnless(lib.HAS_FAST, ...)` raises
# AttributeError while the module imports on the base, so every test in the file -- including
# an unrelated green-on-base one -- counts as red. Only from-imported names are stubbed.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nimport lib\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.add(1, 0), 1)\n",
}
PR = {
    "lib.py": "HAS_FAST = True\n\n\ndef add(a, b):\n    return a + b\n\n\ndef fast_add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + """

class TestAdd(unittest.TestCase):
    def test_old(self):
        self.assertEqual(lib.add(1, 0), 1)

    def test_zero(self):
        self.assertEqual(lib.add(0, 0), 0)   # green on base


@unittest.skipUnless(lib.HAS_FAST, "no accelerator")
class TestFast(unittest.TestCase):
    def test_fast_adds(self):
        self.assertEqual(lib.fast_add(2, 3), 5)
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base"]
EXPECT_NOT = ["RED-FIRST:TestFast"]
