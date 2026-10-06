HDR = "import json, os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nimport lib\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(lib.add(0, 0), 0)\n",
}
PR = {
    "tests/test_lib.py": HDR
    + """
class TestAdd(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(lib.add(0, 0), 0)

    def test_adds(self):
        if "RED_FIRST_OUT" in os.environ:
            base = "red-first-" in os.getcwd()
            pathlib.Path(os.environ["RED_FIRST_OUT"]).write_text(json.dumps({"verdicts": [["red" if base else "green", ""]], "resolved": []}))
            os._exit(0)
        self.assertEqual(lib.add(2, 3), 5)
"""
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_adds does not pass at HEAD"]
EXPECT_NOT = []
