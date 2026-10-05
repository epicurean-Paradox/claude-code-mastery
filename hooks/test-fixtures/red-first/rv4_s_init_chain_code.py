# pkg/ is an implicit namespace package on the base. The PR adds pkg/__init__.py re-exporting a
# new function. The __init__ chain copy puts HEAD's __init__ into the base, which cannot import
# there, so a green-on-base test of existing code counts as red.
T = "import unittest\nfrom pkg.core import add\n\n\nclass TestCore(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n"
BASE = {"pkg/core.py": "def add(a, b):\n    return a - b\n", "pkg/test_core.py": T}
PR = {
    "pkg/__init__.py": "from .core import add, mul\n",
    "pkg/core.py": "def add(a, b):\n    return a + b\n\n\ndef mul(a, b):\n    return a * b\n",
    "pkg/test_core.py": T
    + "\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n",
}
AFTER = [
    "git checkout -q HEAD~1 -- pkg/core.py && git rm -q --cached pkg/__init__.py && mv pkg/__init__.py /tmp/x_init_$$.py; python3 -m unittest pkg.test_core 2>&1 | tail -1"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestCore.test_zero is green on base"]
EXPECT_NOT = []
