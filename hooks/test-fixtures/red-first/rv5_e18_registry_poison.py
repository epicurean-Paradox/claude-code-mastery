# The test module registers handlers at import; one is new (lib.CsvHandler). The learned stub
# lands in lib's registry, and an unrelated green-on-base test that dispatches through the
# registry errors once the stubs arm.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
OLD = "\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n"
ZERO = "\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n"
LIB = "REGISTRY = []\n\n\ndef register(h):\n    REGISTRY.append(h)\n\n\ndef dispatch(kind, x):\n    for h in REGISTRY:\n        if h.accepts(kind):\n            return h.run(x)\n    raise LookupError(kind)\n\n\nclass JsonHandler:\n    @staticmethod\n    def accepts(kind):\n        return kind == 'json'\n\n    @staticmethod\n    def run(x):\n        return x\n"
BASE = {
    "lib.py": LIB,
    "tests/test_lib.py": HDR
    + "import lib\nlib.register(lib.JsonHandler)\n\n\nclass T(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.dispatch('json', 1), 1)\n",
}
PR = {
    "lib.py": LIB
    + "\n\nclass CsvHandler(JsonHandler):\n    @staticmethod\n    def accepts(kind):\n        return kind == 'csv'\n",
    "tests/test_lib.py": HDR
    + "import lib\nlib.register(lib.CsvHandler)\nlib.register(lib.JsonHandler)\n\n\nclass T(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.dispatch('json', 1), 1)\n\n    def test_csv(self):\n        self.assertEqual(lib.dispatch('csv', 2), 2)\n\n    def test_unknown_kind_raises(self):\n        with self.assertRaises(LookupError):\n            lib.dispatch('xml', 1)   # green on base\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["T.test_unknown_kind_raises is green on base"]
EXPECT_NOT = ["RED-FIRST:T.test_csv"]
