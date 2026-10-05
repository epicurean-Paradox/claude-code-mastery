HDR = """\
import json, pathlib, sys, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lib
"""
BASE = {
    "lib.py": "def safe(rec):\n    return True\n",
    "tests/fixtures/records.json": '[{"name": "a"}]\n',
    "tests/test_lib.py": HDR
    + "\nclass TestSafe(unittest.TestCase):\n    def test_plain(self):\n        self.assertTrue(lib.safe({'name': 'a'}))\n",
}
# Honest red-first PR: adds a hostile record to the fixture and a test that every hostile one is refused.
PR = {
    "lib.py": "def safe(rec):\n    return not rec.get('hostile')\n",
    "tests/fixtures/records.json": '[{"name": "a"}, {"name": "b", "hostile": true}]\n',
    "tests/test_lib.py": HDR
    + """
class TestSafe(unittest.TestCase):
    def test_plain(self):
        self.assertTrue(lib.safe({'name': 'a'}))
    def test_hostile_fixture_records_are_refused(self):
        recs = json.loads((HERE / "fixtures" / "records.json").read_text())
        for r in recs:
            self.assertEqual(lib.safe(r), not r.get("hostile"))
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["test_hostile_fixture_records_are_refused: red on base"]
EXPECT_NOT = []
