# PR adds a memoize decorator; the test module decorates a helper with it.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
OLD = "\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n"
ZERO = "\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR + "from lib import add\n" + OLD,
}
PR = {
    "lib.py": "import functools\n\ndef add(a, b):\n    return a + b\n\ndef memoize(f):\n    cache = {}\n    @functools.wraps(f)\n    def g(*a):\n        if a not in cache:\n            cache[a] = f(*a)\n        return cache[a]\n    g.cache = cache\n    return g\n",
    "tests/test_lib.py": HDR
    + "from lib import add, memoize\n\nCALLS = []\n\n@memoize\ndef counted_add(a, b):\n    CALLS.append((a, b))\n    return add(a, b)\n"
    + OLD
    + "\n    def test_second_call_is_cached(self):\n        counted_add(1, 2)\n        counted_add(1, 2)\n        self.assertEqual(len(CALLS), 1)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestAdd.test_second_call_is_cached: error on base"]
EXPECT_NOT = ["RED-FIRST:"]
