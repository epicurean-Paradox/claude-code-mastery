HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + """
class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(lib.add(0, 0), 0)
""",
}
# Honest red-first PR: adds lib.Store and a class whose setUpClass builds one.
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\nclass Store:\n    def __init__(self):\n        self.items = [lib_item for lib_item in (1, 2)]\n",
    "tests/test_lib.py": HDR
    + """
class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(lib.add(0, 0), 0)

class TestStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = lib.Store()
    def test_store_has_two(self):
        self.assertEqual(len(self.store.items), 2)
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["setUpClass"]
EXPECT_NOT = []
