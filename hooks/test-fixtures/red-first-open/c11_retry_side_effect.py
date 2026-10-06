# A statement retried after learning re-runs the side effects it had before the escape.
HDR = "import os, pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "SEEN = []\n\n\ndef track(x):\n    SEEN.append(x)\n    return x\n",
    "tests/test_lib.py": HDR
    + "import lib\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.track(1), 1)\n",
}
PR = {
    "lib.py": "SEEN = []\n\n\ndef track(x):\n    SEEN.append(x)\n    return x\n\n\nLIMIT = 3\n",
    "tests/test_lib.py": HDR
    + "import lib\n\n\nclass Config:\n    first = lib.track('config')\n    limit = lib.LIMIT\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.track(1), 1)\n\n    def test_limit(self):\n        self.assertEqual(Config.limit, 3)\n\n    def test_tracked_once(self):\n        self.assertEqual(lib.SEEN.count('config'), 1)   # green on base\n",
}
