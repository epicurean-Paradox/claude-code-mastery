HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lib import add
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + """
class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(add(0, 0), 0)
""",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + """
class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(add(0, 0), 0)

    if sys.version_info >= (3, 8):
        def test_green_on_base(self):
            self.assertEqual(add(1, 1) * 0, 0)
""",
}
AFTER = [
    "git stash -q 2>/dev/null; python3 -m unittest discover -v -s tests -p test_lib.py 2>&1 | grep -E '^test_'"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_green_on_base is green on base"]
EXPECT_NOT = []
