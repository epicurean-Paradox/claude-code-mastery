HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n",
    "tests/test_math.py": HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(lib.add(2, 3), 5)\n\nclass TestMul(unittest.TestCase):\n    def test_mul(self):\n        self.assertEqual(lib.mul(2, 3), 6)\n",
    "tests/test_other.py": HDR
    + "\nclass TestOther(unittest.TestCase):\n    def test_o(self):\n        pass\n",
}
# Pure refactor: TestMul moves from test_math.py into test_other.py. No code change.
PR = {
    "tests/test_math.py": HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(lib.add(2, 3), 5)\n",
    "tests/test_other.py": HDR
    + "\nclass TestOther(unittest.TestCase):\n    def test_o(self):\n        pass\n\nclass TestMul(unittest.TestCase):\n    def test_mul(self):\n        self.assertEqual(lib.mul(2, 3), 6)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["renamed, not new"]
EXPECT_NOT = []
