# The repo's test directory is `test/` (not `tests/`). The PR adds a helper there and a new test
# that is green on the base's product code.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "test/helpers.py": "def pair():\n    return (1, 0)\n",
    "test/test_lib.py": HDR
    + "from lib import add\nfrom helpers import pair\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(*pair()), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b  # refactor\n",
    "test/helpers.py": "def pair():\n    return (1, 0)\n\n\ndef zeros():\n    return (0, 0)\n",
    "test/test_lib.py": HDR
    + "from lib import add\nfrom helpers import pair, zeros\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(*pair()), 1)\n\n    def test_zero(self):\n        self.assertEqual(add(*zeros()), 0)   # green on base\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base"]
EXPECT_NOT = []
