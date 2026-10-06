# Cascade: a skipped if-block binds its methods' LOCAL names (`result`) as derived; a second
# if-block whose class never touches a stub but also assigns a local `result` is then skipped
# too, and its honest red-first test is "not collected".
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b if b else a\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n",
    "tests/test_lib.py": HDR
    + "from lib import add, mul\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n\nif sys.version_info >= (3, 8):\n    class TestMul(unittest.TestCase):\n        def test_mul(self):\n            result = mul(2, 3)\n            self.assertEqual(result, 6)\n\n\nif os.name != 'nope':\n    class TestAddFix(unittest.TestCase):\n        def test_add_fixed(self):\n            result = add(2, 3)\n            self.assertEqual(result, 5)   # red on base: the bug\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = [
    "TestAddFix.test_add_fixed: red on base",
    "TestMul.test_mul: error on base (missing on base: lib.mul)",
]
EXPECT_NOT = ["RED-FIRST:"]
