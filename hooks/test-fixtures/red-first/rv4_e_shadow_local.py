# The PR adds lib.config; a new test binds its own local `config` and never touches lib.config.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR
    + "from lib import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\nconfig = {'strict': True}\n",
    "tests/test_lib.py": HDR
    + """from lib import add, config


class TestAdd(unittest.TestCase):
    def test_old(self):
        self.assertEqual(add(1, 0), 1)

    def test_config_strict(self):
        self.assertTrue(config["strict"])

    def test_zero(self):
        for config in ({"a": 0},):
            self.assertEqual(add(config["a"], 0), 0)   # green on base
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = [
    "TestAdd.test_zero is green on base",
    "TestAdd.test_config_strict: error on base (missing on base: lib.config)",
]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_config_strict"]
