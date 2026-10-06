# `from newmod import *` of a module the PR adds: on the base the stub carries every name HEAD's
# newmod has, re-exports included (`add`, `os`), and rebinds the test module's real ones.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "newmod.py": "import os\nfrom lib import add\n\n\ndef double(x):\n    return add(x, x)\n",
    "tests/test_lib.py": HDR
    + "from lib import add\nfrom newmod import *\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_double(self):\n        self.assertEqual(double(2), 4)\n\n    def test_add_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n\n    def test_cwd(self):\n        self.assertTrue(os.path.isdir(os.getcwd()))   # green on base\n",
}
