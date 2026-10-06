# unittest's runner installs the 'default' warnings filter; the driver runs the suite
# without it, so DeprecationWarning raised from library code is ignored, and a test that
# records it with catch_warnings(record=True) fails at HEAD.
HDR = """\
import pathlib, sys, unittest, warnings
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def old_api():\n    return 1\n",
    "tests/test_lib.py": HDR
    + "\nclass TestOld(unittest.TestCase):\n    def test_value(self):\n        self.assertEqual(lib.old_api(), 1)\n",
}
PR = {
    "lib.py": "import warnings\n\ndef old_api():\n    warnings.warn('old_api is deprecated', DeprecationWarning, stacklevel=2)\n    return 1\n",
    "tests/test_lib.py": HDR
    + """
class TestOld(unittest.TestCase):
    def test_value(self):
        self.assertEqual(lib.old_api(), 1)
    def test_old_api_warns(self):
        with warnings.catch_warnings(record=True) as caught:
            lib.old_api()
        self.assertEqual([w.category for w in caught], [DeprecationWarning])
""",
}
AFTER = [
    "python3 -m unittest discover -v -s tests 2>&1 | grep -E '^test_|^Ran|^OK|^FAILED'"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestOld.test_old_api_warns: red on base"]
EXPECT_NOT = []
