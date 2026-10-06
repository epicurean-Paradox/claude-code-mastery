# `test/` holds a helper module; the tests live in test/unit/. A changed helper is not copied
# (test/ itself holds no test file), so a new green-on-base test that uses a new helper errors.
BASE = {
    "lib.py": "def parse(s):\n    return s.split(',')\n",
    "test/__init__.py": "",
    "test/helpers.py": "def row():\n    return 'a,b'\n",
    "test/unit/__init__.py": "",
    "test/unit/test_lib.py": "import unittest\nfrom lib import parse\nfrom test.helpers import row\n\n\nclass TestParse(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(parse(row()), ['a', 'b'])\n",
}
PR = {
    "test/helpers.py": "def row():\n    return 'a,b'\n\n\ndef empty_row():\n    return 'x'\n",
    "test/unit/test_lib.py": "import unittest\nfrom lib import parse\nfrom test.helpers import row, empty_row\n\n\nclass TestParse(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(parse(row()), ['a', 'b'])\n\n    def test_single(self):\n        self.assertEqual(parse(empty_row()), ['x'])   # green on base\n",
}
