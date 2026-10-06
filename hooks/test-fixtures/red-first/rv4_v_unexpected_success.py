# A "known bug" marker: expectedFailure until lib says the bug is fixed. The test itself is green
# on the base (it cannot see the bug); on the base it is an unexpected success, printed as plain
# "red on base" -- the detail is dropped.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nimport lib\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.add(1, 0), 1)\n",
}
PR = {
    "lib.py": "BUG_123_FIXED = True\n\n\ndef add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + """
known_bug = (lambda f: f) if getattr(lib, "BUG_123_FIXED", False) else unittest.expectedFailure


class TestAdd(unittest.TestCase):
    def test_old(self):
        self.assertEqual(lib.add(1, 0), 1)

    @known_bug
    def test_zero(self):
        self.assertEqual(lib.add(0, 0), 0)
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base (unexpected success)"]
EXPECT_NOT = []
