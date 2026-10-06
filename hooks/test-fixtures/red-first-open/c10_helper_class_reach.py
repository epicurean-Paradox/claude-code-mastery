# Honest test reaching a stub-derived global through a module-level helper CLASS (not a
# function): the reach walk does not follow it, the stub flows out unused, and the test passes.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\n\ndef load_plugins():\n    return {'csv': object()}\n",
    "tests/test_lib.py": HDR
    + "from lib import add, load_plugins\n\nCSV = load_plugins()['csv']\n\n\nclass Fixtures:\n    def csv(self):\n        return CSV\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_csv_plugin_loaded(self):\n        self.assertIsNotNone(Fixtures().csv())\n",
}
