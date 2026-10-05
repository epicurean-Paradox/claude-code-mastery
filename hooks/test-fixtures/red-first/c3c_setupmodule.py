HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_store.py": HDR
    + "\nclass TestX(unittest.TestCase):\n    def test_x(self):\n        pass\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef init_db():\n    return {}\n",
    "tests/test_store.py": HDR
    + """
DB = None
def setUpModule():
    global DB
    DB = lib.init_db()

class TestX(unittest.TestCase):
    def test_x(self):
        pass
    def test_db_empty(self):
        self.assertEqual(DB, {})
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["setUpModule"]
EXPECT_NOT = []
