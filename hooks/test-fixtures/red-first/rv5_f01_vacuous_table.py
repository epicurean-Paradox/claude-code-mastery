# Honest table-driven test of a module the PR adds: on the real base the module is missing (error).
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
OLD = "\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n"
ZERO = "\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR + "from lib import add\n" + OLD,
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "codes.py": "TABLE = {'ok': 200, 'missing': 404}\n\ndef status(name):\n    return TABLE[name]\n",
    "tests/test_lib.py": HDR
    + "from lib import add\nimport codes\nCASES = dict(codes.TABLE)\n"
    + OLD
    + "\n    def test_every_code_resolves(self):\n        for name, code in CASES.items():\n            with self.subTest(name):\n                self.assertEqual(codes.status(name), code)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestAdd.test_every_code_resolves: error on base"]
EXPECT_NOT = ["RED-FIRST:"]
