# Feature detection with hasattr after one new attribute escaped: the bulk stub answers hasattr.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "import lib\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\nLIMIT = 3\n\ndef fast_add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "import lib\nLIMIT = lib.LIMIT\nHAS_FAST = hasattr(lib, 'fast_add')\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.add(1, 0), 1)\n\n    def test_limit(self):\n        self.assertEqual(LIMIT, 3)\n\n    def test_add_zero(self):\n        impl = lib.fast_add if HAS_FAST else lib.add\n        self.assertEqual(impl(0, 0), 0)   # green on base: falls back to add\n",
}
