# A latin-1 test file (coding cookie): on the base the driver re-reads it as UTF-8 with
# replacement, so a non-ASCII literal changes and a green-on-base test goes red.
HDR = "# -*- coding: latin-1 -*-\nimport os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef name():\n    return 'caf' + chr(0xC3) + chr(0xA9)\n",
    "tests/test_lib.py": HDR
    + "from lib import add, name\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef name():\n    return 'caf' + chr(0xC3) + chr(0xA9)\n",
    "tests/test_lib.py": HDR
    + "from lib import add, name\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_name(self):\n        self.assertEqual(name(), 'caf\xe9')   # green on base\n",
}
