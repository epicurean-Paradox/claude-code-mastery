# r07 with a relative import: TestRoundtrip moves from tests/json/ to tests/toml/ (both files
# keep other tests, so git sees no rename). `from .codec import dumps, loads` is the same text
# and the same AST in both files but names a different module. The pairing calls it a rename;
# the TOML test is never run, and it is green on the base.
IMP = "import unittest\nfrom .codec import dumps, loads\n\n\n"
RT = "class TestRoundtrip(unittest.TestCase):\n    def test_empty(self):\n        self.assertEqual(loads(dumps({})), {})\n"
KEEP = "class TestKeep%s(unittest.TestCase):\n    def test_k(self):\n        pass\n\n\n"
BASE = {
    "tests/__init__.py": "",
    "tests/json/__init__.py": "",
    "tests/toml/__init__.py": "",
    "tests/json/codec.py": "import json\ndumps, loads = json.dumps, json.loads\n",
    "tests/toml/codec.py": "def dumps(d):\n    return ''\n\n\ndef loads(s):\n    return {}\n",
    "tests/json/test_codec.py": IMP + KEEP % "J" + RT,
    "tests/toml/test_codec.py": IMP + KEEP % "T",
}
PR = {
    "tests/json/test_codec.py": IMP + KEEP % "J",
    "tests/toml/test_codec.py": IMP + KEEP % "T" + RT,
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestRoundtrip.test_empty is green on base"]
EXPECT_NOT = ["renamed"]
