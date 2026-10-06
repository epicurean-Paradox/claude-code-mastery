HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
OLD = "\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n"
ZERO = "\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n"
N = 70
consts = "".join(f"E{i} = {i}\n" for i in range(N))
names = ", ".join(f"E{i}" for i in range(N))
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR + "from lib import add\n" + OLD,
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\n" + consts,
    "tests/test_lib.py": HDR
    + f"from lib import add\nfrom lib import ({names})\n"
    + OLD
    + ZERO
    + "\n    def test_codes(self):\n        self.assertEqual(E69, 69)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base", "TestAdd.test_codes: error on base"]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_codes"]
