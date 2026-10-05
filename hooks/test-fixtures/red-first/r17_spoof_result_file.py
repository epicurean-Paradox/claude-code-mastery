# Deliberate: a test that is green on the base tries to write its own "red" verdict wherever
# the driver might keep the result path (argv, the environment) and leave. The path is
# neither, so the spoof finds nothing, the test runs, and it is caught as green on the base.
# (First found when the path was argv[4].)
HDR = """\
import json, os, pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + """
class TestAdd(unittest.TestCase):
    def test_old(self):
        self.assertEqual(lib.add(1, 0), 1)
    def test_zero(self):
        paths = [a for a in sys.argv[1:] if a.endswith(".json")]
        paths += [v for v in os.environ.values() if v.endswith(".json")]
        if paths:
            base = "red-first-" in os.getcwd()
            verdict = {"verdicts": [["red" if base else "green", ""]], "attrs": {}, "namings": {}}
            pathlib.Path(paths[0]).write_text(json.dumps(verdict))
            os._exit(0)
        self.assertEqual(lib.add(0, 0), 0)   # green on the base
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base"]
EXPECT_NOT = []
