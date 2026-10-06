# Code under test optionally uses an accelerator module; the PR adds it. On the base lib falls
# back to pure python. The test imports the new module first (isort: _accel < lib).
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
LIB = "try:\n    import _accel\nexcept ImportError:\n    _accel = None\n\n\ndef add(a, b):\n    if _accel:\n        return _accel.add(a, b)\n    return a + b\n"
BASE = {
    "lib.py": LIB,
    "tests/test_lib.py": HDR
    + "import lib\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.add(1, 0), 1)\n",
}
PR = {
    "_accel.py": "def add(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR
    + "import _accel\nimport lib\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(lib.add(1, 0), 1)\n\n    def test_accel(self):\n        self.assertEqual(_accel.add(2, 3), 5)\n\n    def test_zero(self):\n        self.assertEqual(lib.add(0, 0), 0)   # green on base: lib falls back\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base"]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_accel"]
