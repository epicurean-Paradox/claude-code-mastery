# test_b.py has its OWN class named Tests (subclassed there) and imports a name only HEAD has.
# It never runs test_a's test, but it is loaded as a "subclass file" and its load error on the
# base turns test_a's green-on-base test red.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_a.py": HDR
    + "from lib import add\n\n\nclass Tests(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
    "tests/test_b.py": HDR
    + "from lib import add\n\n\nclass Tests(unittest.TestCase):\n    def test_b(self):\n        self.assertEqual(add(1, 0), 1)\n\n\nclass MoreTests(Tests):\n    pass\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\n\ndef mul(a, b):\n    return a * b\n",
    "tests/test_a.py": HDR
    + "from lib import add\n\n\nclass Tests(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n",
    "tests/test_b.py": HDR
    + "from lib import add, mul\n\n\nclass Tests(unittest.TestCase):\n    def test_b(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_mul(self):\n        self.assertEqual(mul(2, 3), 6)\n\n\nclass MoreTests(Tests):\n    pass\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["tests/test_a.py:RED-FIRST:Tests.test_zero is green on base"]
EXPECT_NOT = ["tests/test_b.py:RED-FIRST"]
