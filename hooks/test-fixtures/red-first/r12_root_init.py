# The repository root is itself a package (an add-on / plugin repo); tests run with
# `python -m unittest discover` from the root. The driver walks above the repo root.
T = "import unittest\nfrom lib import add\n\nclass TestAdd(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)\n"
BASE = {
    "__init__.py": "",
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/__init__.py": "",
    "tests/test_lib.py": T,
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": T
    + "    def test_adds(self):\n        self.assertEqual(add(2, 3), 5)\n",
}
AFTER = ["python3 -m unittest discover -v 2>&1 | grep -E '^test_|^Ran|^OK|^FAILED'"]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestAdd.test_adds: red on base"]
EXPECT_NOT = []
DIRNAME = "my.repo"
