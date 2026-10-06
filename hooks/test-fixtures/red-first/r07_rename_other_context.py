# PR drops JSON support (deletes tests/test_json.py) and adds TOML support with a new test
# file. Both files use the conventional class name and an identical body bound to a
# different module-level codec. The "move" pairing treats the TOML test as a rename, so it
# is never run, though it tests a different function and is green on the base.
T = """\
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from %s import dumps, loads

class TestRoundtrip(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(loads(dumps({})), {})
"""
BASE = {
    "codec_json.py": "import json\ndumps, loads = json.dumps, json.loads\n",
    "codec_toml.py": "def dumps(d):\n    return ''\n\ndef loads(s):\n    return {}\n",
    "tests/test_json.py": T % "codec_json",
}
PR = {
    "codec_json.py": None,
    "tests/test_json.py": None,
    "tests/test_toml.py": '"""TOML codec tests.\n\n'
    + "Covers the TOML codec added in this change.\n" * 12
    + '"""\n'
    + T % "codec_toml",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestRoundtrip.test_empty is green on base"]
EXPECT_NOT = ["renamed"]
