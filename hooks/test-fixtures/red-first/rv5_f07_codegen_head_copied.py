# A gitignored generated module (built from a tracked generator in CI). The PR fixes the
# generator; the checkout's generated file (HEAD's build) is copied into the base.
BASE = {
    ".gitignore": "pkg/_tables.py\n",
    "pkg/__init__.py": "",
    "gen.py": "OUT = 'pkg/_tables.py'\nSQUARES = {i: i * i for i in range(5)}\nSQUARES[4] = 15  # bug\n",
    "pkg/_tables.py": "SQUARES = {0: 0, 1: 1, 2: 4, 3: 9, 4: 15}\n",
    "pkg/core.py": "from pkg._tables import SQUARES\n\ndef square(n):\n    return SQUARES[n]\n",
    "tests/test_core.py": "import unittest\nfrom pkg.core import square\n\n\nclass TestSq(unittest.TestCase):\n    def test_two(self):\n        self.assertEqual(square(2), 4)\n",
}
PR = {
    "gen.py": "OUT = 'pkg/_tables.py'\nSQUARES = {i: i * i for i in range(5)}\n",
    "pkg/_tables.py": "SQUARES = {0: 0, 1: 1, 2: 4, 3: 9, 4: 16}\n",
    "tests/test_core.py": "import unittest\nfrom pkg.core import square\n\n\nclass TestSq(unittest.TestCase):\n    def test_two(self):\n        self.assertEqual(square(2), 4)\n\n    def test_four(self):\n        self.assertEqual(square(4), 16)   # red on the real base (15)\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestSq.test_four is green on base"]
EXPECT_NOT = []
