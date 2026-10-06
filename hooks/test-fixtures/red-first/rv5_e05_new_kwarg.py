HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
OLD = "\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n"
ZERO = "\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n\nclass Client:\n    def __init__(self):\n        self.retries = 1\n",
    "tests/test_lib.py": HDR + "from lib import add, Client\n" + OLD,
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\nclass Client:\n    def __init__(self, retries=1):\n        self.retries = retries\n",
    "tests/test_lib.py": HDR
    + "from lib import add, Client\nCLIENT = Client(retries=3)\n"
    + OLD
    + ZERO
    + "\n    def test_retries(self):\n        self.assertEqual(CLIENT.retries, 3)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base", "TestAdd.test_retries: error on base"]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_retries"]
