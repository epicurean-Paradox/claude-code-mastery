BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lib import add

class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(add(0, 0), 0)
""",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n",
    "tests/test_lib.py": """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lib import add, mul

class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(add(0, 0), 0)
    def test_add_negatives_zero(self):
        self.assertEqual(add(-1, -1) * 0, 0)   # green on the base: cannot see the a-b bug
    def test_mul(self):
        self.assertEqual(mul(2, 3), 6)
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = [
    "TestAdd.test_add_negatives_zero is green on base",
    "missing on base: lib.mul",
]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_mul"]
