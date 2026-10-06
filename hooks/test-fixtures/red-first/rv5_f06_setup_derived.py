# rv4_i (stub-derived global, identity-style assertion) reached through setUp instead of the body.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
OLD = "\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n"
ZERO = "\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR + "from lib import add\n" + OLD,
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\n\ndef load_plugins():\n    return {'csv': object()}\n",
    "tests/test_lib.py": HDR
    + "from lib import add, load_plugins\n\nCSV = load_plugins()['csv']\n"
    + OLD
    + "\n\nclass TestPlugins(unittest.TestCase):\n    def setUp(self):\n        self.csv = CSV\n\n    def test_csv_plugin_loaded(self):\n        self.assertIsNotNone(self.csv)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestPlugins.test_csv_plugin_loaded: error on base"]
EXPECT_NOT = ["RED-FIRST:"]
