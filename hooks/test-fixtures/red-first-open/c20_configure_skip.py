# A module-level configure call passes one new option: the whole call is skipped on the base, so
# the old strict option is lost too and a green-on-base test of strict validation goes red.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
LIB = "OPTS = {}\n\n\ndef configure(**opts):\n    OPTS.update(opts)\n\n\ndef validate(x):\n    if OPTS.get('strict') and x < 0:\n        raise ValueError(x)\n    return x\n"
BASE = {
    "lib.py": LIB,
    "tests/test_lib.py": HDR
    + "import lib\nlib.configure(strict=True)\n\n\nclass TestV(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.validate(1), 1)\n",
}
PR = {
    "lib.py": LIB + "\n\nFAST_DEFAULT = True\n",
    "tests/test_lib.py": HDR
    + "import lib\nlib.configure(strict=True, fast=lib.FAST_DEFAULT)\n\n\nclass TestV(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.validate(1), 1)\n\n    def test_fast_default(self):\n        self.assertTrue(lib.FAST_DEFAULT)\n\n    def test_negative_rejected(self):\n        with self.assertRaises(ValueError):\n            lib.validate(-1)   # green on base: strict was already enforced\n",
}
