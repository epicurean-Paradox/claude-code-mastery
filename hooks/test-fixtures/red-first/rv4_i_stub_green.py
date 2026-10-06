# Honest red-first tests that read the new name through a module-level constant: the stub
# absorbed the import-time use and the assertions never touch it again, so they pass on base.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\n\ndef load_plugins():\n    return {'csv': object()}\n\n\nHANDLERS = (add,)\n",
    "tests/test_lib.py": HDR
    + """from lib import add, load_plugins

PLUGINS = load_plugins()
CSV = PLUGINS["csv"]


class TestAdd(unittest.TestCase):
    def test_old(self):
        self.assertEqual(add(1, 0), 1)

    def test_csv_plugin_loaded(self):
        self.assertIsNotNone(CSV)

    def test_csv_plugin_is_an_object(self):
        self.assertIsInstance(CSV, object)
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = [
    "TestAdd.test_csv_plugin_loaded: error on base (missing on base: lib.load_plugins)"
]
EXPECT_NOT = ["RED-FIRST:"]
