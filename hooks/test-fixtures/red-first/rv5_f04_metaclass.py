HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
OLD = "\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n"
ZERO = "\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n"
    + OLD.replace("add(1, 0), 1", "add(0, 0), 0"),
}
PR = {
    "lib.py": "import abc\n\ndef add(a, b):\n    return a + b\n\nclass Registered(type(__import__('unittest').TestCase)):\n    pass\n",
    "tests/test_lib.py": HDR
    + "from lib import add, Registered\n"
    + OLD.replace("add(1, 0), 1", "add(0, 0), 0")
    + "\n\nclass TestReg(unittest.TestCase, metaclass=Registered):\n    def test_adds(self):\n        self.assertEqual(add(2, 3), 5)   # red on base: add subtracts\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestReg.test_adds: error on base"]
EXPECT_NOT = ["RED-FIRST:"]
