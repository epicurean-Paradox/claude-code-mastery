# rv5_e18 (registry poison) through getattr in a loop: the statement does not NAME the stub, so it
# is retried, not skipped; the retry registers the old handler twice and the stub once, into lib.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
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
    + "import lib\nfor name in ('JsonHandler', 'CsvHandler'):\n    lib.register(getattr(lib, name))\n\n\nclass T(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.dispatch('json', 1), 1)\n\n    def test_csv(self):\n        self.assertEqual(lib.dispatch('csv', 2), 2)\n\n    def test_unknown_kind_raises(self):\n        with self.assertRaises(LookupError):\n            lib.dispatch('xml', 1)   # green on base\n",
}
