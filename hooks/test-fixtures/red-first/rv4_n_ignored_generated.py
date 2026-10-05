# pkg/_version.py is generated at build time and gitignored (setuptools-scm, protobuf stubs,
# a compiled extension). The checkout has it; the base worktree does not, so the package
# cannot import there and every new test counts as red.
BASE = {
    ".gitignore": "pkg/_version.py\n",
    "pkg/__init__.py": "from ._version import version\n",
    "pkg/_version.py": "version = '1.0'\n",
    "pkg/core.py": "def add(a, b):\n    return a - b\n",
    "tests/test_core.py": "import unittest\nfrom pkg.core import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "pkg/core.py": "def add(a, b):\n    return a + b\n",
    "tests/test_core.py": "import unittest\nfrom pkg.core import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n",
}
AFTER = [
    "git checkout -q HEAD~1 -- pkg/core.py && python3 -m unittest tests.test_core 2>&1 | tail -1; git checkout -q HEAD -- pkg/core.py"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base"]
EXPECT_NOT = []
