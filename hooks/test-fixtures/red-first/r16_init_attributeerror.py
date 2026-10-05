# A TestCase whose __init__ builds the new client; on the base that raises AttributeError,
# which the driver reads as "not collected" -- a violation no pin can excuse.
HDR = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(lib.add(2, 3), 5)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\nclass Client:\n    def get(self):\n        return 200\n",
    "tests/test_lib.py": HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(lib.add(2, 3), 5)\n\nclass TestClient(unittest.TestCase):\n    def __init__(self, *a, **kw):\n        super().__init__(*a, **kw)\n        self.client = lib.Client()\n\n    def test_get(self):\n        self.assertEqual(self.client.get(), 200)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestClient.test_get: error on base"]
EXPECT_NOT = []
