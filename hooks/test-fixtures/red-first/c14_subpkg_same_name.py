HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
T = (
    HDR
    + "\nclass TestApi(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(lib.add(0, 0), 0)\n"
)
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_api.py": T,
    "tests/v2/__init__.py": "",
    "tests/v2/test_api.py": HDR.replace("parents[1]", "parents[2]")
    + "\nclass TestApi(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(lib.add(0, 0), 0)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_api.py": T
    + "    def test_adds(self):\n        self.assertEqual(lib.add(2, 3), 5)\n",
    "tests/v2/test_api.py": HDR.replace("parents[1]", "parents[2]")
    + "\nclass TestApi(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(lib.add(0, 0), 0)\n    def test_adds(self):\n        self.assertEqual(lib.add(2, 3), 5)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = []
EXPECT_NOT = ["not collected"]
