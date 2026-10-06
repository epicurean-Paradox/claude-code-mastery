# PR adds a new test subpackage (its __init__.py is not a test file, so it is not copied
# into the base worktree). The test uses a relative import of EXISTING code and is green
# on the base, but on the base it loads as a top-level module and the relative import fails.
T = "import unittest\nfrom ...core import add\n\nclass TestCore(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)\n"
BASE = {
    "pkg/__init__.py": "",
    "pkg/tests/__init__.py": "",
    "pkg/core.py": "def add(a, b):\n    return a - b\n",
    "pkg/tests/test_core.py": "import unittest\nfrom ..core import add\n\nclass TestOld(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)\n",
}
PR = {
    "pkg/core.py": "def add(a, b):\n    return a - b\n\ndef unused():\n    pass\n",
    "pkg/tests/unit/__init__.py": "",
    "pkg/tests/unit/test_core.py": T
    + "    def test_negatives_times_zero(self):\n        self.assertEqual(add(-1, -1) * 0, 0)   # green on the base\n",
}
AFTER = [
    "git checkout -q HEAD~1 -- pkg/core.py && python3 -m unittest -v pkg.tests.unit.test_core 2>&1 | grep -E '^test_|^OK|^FAILED'; git checkout -q HEAD -- ."
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestCore.test_negatives_times_zero is green on base"]
EXPECT_NOT = []
