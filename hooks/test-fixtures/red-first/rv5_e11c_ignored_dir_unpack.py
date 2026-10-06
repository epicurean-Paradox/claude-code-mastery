# Generated package in an ignored DIRECTORY; the base worktree does not get it (--directory
# collapses gen/), and the stub cannot absorb the unpacking in pkg/__init__.
BASE = {
    ".gitignore": "gen/\n",
    "gen/__init__.py": "",
    "gen/version.py": "version = '1.0'\n",
    "pkg/__init__.py": "from gen.version import version\nMAJOR, MINOR = version.split('.')\n",
    "pkg/core.py": "def add(a, b):\n    return a - b\n",
    "tests/test_core.py": "import unittest\nfrom pkg.core import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "pkg/core.py": "def add(a, b):\n    return a + b\n",
    "tests/test_core.py": "import unittest\nfrom pkg.core import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base"]
EXPECT_NOT = []
