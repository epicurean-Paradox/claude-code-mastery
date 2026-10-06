# A module constant annotated with a new type under `from __future__ import annotations`: the
# annotation is never evaluated, but the statement NAMES the stub and is skipped.
HDR = "from __future__ import annotations\nimport os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef parse(s):\n    return s.split(',')\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef parse(s):\n    return s.split(',')\n\nclass Row(list):\n    pass\n",
    "tests/test_lib.py": HDR
    + "from lib import add, parse, Row\n\nSAMPLE: Row = parse('a,b')\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_row_type(self):\n        self.assertTrue(issubclass(Row, list))\n\n    def test_sample_parses(self):\n        self.assertEqual(SAMPLE, ['a', 'b'])   # green on base\n",
}
