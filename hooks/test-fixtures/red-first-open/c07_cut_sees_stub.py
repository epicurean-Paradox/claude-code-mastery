# Code under test reads settings by name. The test module's first lookup of a NEW setting
# escapes from lib (importer = lib), so every name settings gains is stubbed FOR lib: a later
# import-time lib.get(..., default) of another new setting returns a stub instead of the default.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
LIB = "import settings\n\n\ndef get(name, default=None):\n    return getattr(settings, name, default) if default is not None else getattr(settings, name)\n\n\ndef add(a, b):\n    return a + b\n"
BASE = {
    "settings.py": "DEBUG = False\n",
    "lib.py": LIB,
    "tests/test_lib.py": HDR
    + "import lib\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.add(1, 0), 1)\n",
}
PR = {
    "settings.py": "DEBUG = False\nTIMEOUT = 5\nRETRIES = 0\n",
    "lib.py": LIB,
    "tests/test_lib.py": HDR
    + "import lib\nTIMEOUT = lib.get('TIMEOUT')\nRETRIES = lib.get('RETRIES', 0)\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.add(1, 0), 1)\n\n    def test_timeout(self):\n        self.assertEqual(TIMEOUT, 5)\n\n    def test_no_retries(self):\n        self.assertEqual(RETRIES, 0)   # green on base: the default\n",
}
