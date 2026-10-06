# Same with the class in a try block (an optional dependency guard), and the new name only in another class.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b if b else a\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n",
    "tests/test_lib.py": HDR
    + "from lib import add, mul\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n\ntry:\n    import json\nexcept ImportError:\n    json = None\nelse:\n    class TestJson(unittest.TestCase):\n        def test_add_fixed(self):\n            self.assertEqual(add(2, 3), 5)   # red on base: the bug\n\n        def test_mul_json(self):\n            self.assertEqual(json.loads(str(mul(2, 3))), 6)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = [
    "TestJson.test_add_fixed: red on base",
    "TestJson.test_mul_json: error on base (missing on base: lib.mul)",
]
EXPECT_NOT = ["RED-FIRST:"]
