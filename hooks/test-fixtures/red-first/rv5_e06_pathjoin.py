HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
OLD = "\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n"
ZERO = "\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR + "import lib\nfrom lib import add\n" + OLD,
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\nCONFIG_NAME = 'app.toml'\n",
    "tests/test_lib.py": HDR
    + "import lib\nfrom lib import add\nCONF = os.path.join(os.path.dirname(__file__), lib.CONFIG_NAME)\n"
    + OLD
    + ZERO
    + "\n    def test_conf(self):\n        self.assertTrue(CONF.endswith('app.toml'))\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base", "TestAdd.test_conf: error on base"]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_conf"]
