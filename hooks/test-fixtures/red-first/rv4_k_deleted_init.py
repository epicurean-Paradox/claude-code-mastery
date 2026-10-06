# The PR deletes tests/__init__.py (moving to a `discover -s tests` layout). Deletions are not
# applied to the base worktree, so there the module imports as tests.test_b and its bare sibling
# import fails: a green-on-base test counts as red.
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/__init__.py": "",
    "tests/test_a.py": "import unittest\nfrom lib import add\n\n\nclass TestA(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/__init__.py": None,
    "tests/helpers.py": "ZERO = 0\n",
    "tests/test_b.py": "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nimport helpers\nfrom lib import add\n\n\nclass TestB(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(add(helpers.ZERO, 0), 0)\n",
}
AFTER = [
    "git checkout -q HEAD~1 -- lib.py && python3 -m unittest discover -s tests 2>&1 | tail -1; git checkout -q HEAD -- lib.py"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestB.test_zero is green on base"]
EXPECT_NOT = []
