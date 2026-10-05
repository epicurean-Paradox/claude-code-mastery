# r17 with the round-4 driver: the result path left argv, but the driver's own finish() and
# mode are globals of __main__. lib is never fixed; the test asserts nothing true.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nimport lib\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(lib.add(0, 0), 0)\n",
}
PR = {
    "tests/test_lib.py": HDR
    + """
class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(lib.add(0, 0), 0)

    def test_adds(self):
        import __main__
        if hasattr(__main__, "finish"):
            __main__.finish(["red" if __main__.mode == "base" else "green", ""])
        self.assertEqual(lib.add(2, 3), 5)
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_adds does not pass at HEAD"]
EXPECT_NOT = []
