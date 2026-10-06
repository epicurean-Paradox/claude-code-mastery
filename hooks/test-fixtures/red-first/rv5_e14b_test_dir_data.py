# test/ directory; PR changes a data file there; new test reads it and is green on base code.
HDR = "import json, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nDATA = json.loads((pathlib.Path(__file__).parent / 'data' / 'cases.json').read_text())\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "test/data/cases.json": '{"old": [1, 0, 1]}\n',
    "test/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        a, b, c = DATA['old']\n        self.assertEqual(add(a, b), c)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b  # refactor\n",
    "test/data/cases.json": '{"old": [1, 0, 1], "zero": [0, 0, 0]}\n',
    "test/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        a, b, c = DATA['old']\n        self.assertEqual(add(a, b), c)\n\n    def test_zero(self):\n        a, b, c = DATA['zero']\n        self.assertEqual(add(a, b), c)   # green on base code\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base"]
EXPECT_NOT = []
