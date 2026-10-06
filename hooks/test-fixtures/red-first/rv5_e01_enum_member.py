HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
OLD = "\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n"
ZERO = "\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n"
BASE = {
    "lib.py": "import enum\nclass Color(enum.Enum):\n    RED = 1\n\ndef add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR + "from lib import add, Color\n" + OLD,
}
PR = {
    "lib.py": "import enum\nclass Color(enum.Enum):\n    RED = 1\n    PURPLE = 2\n\ndef add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "from lib import add, Color\nDEFAULT = Color.PURPLE\n"
    + OLD
    + ZERO
    + "\n    def test_purple(self):\n        self.assertEqual(DEFAULT.value, 2)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base", "TestAdd.test_purple: error on base"]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_purple"]
