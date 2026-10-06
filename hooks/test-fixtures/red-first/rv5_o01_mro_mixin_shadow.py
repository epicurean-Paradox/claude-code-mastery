# Runner's MRO has an unrelated mixin that defines test_zero earlier than Contract.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nfrom lib import add\n"
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n",
    "tests/test_c.py": HDR
    + "\n\nclass Other:\n    def test_zero(self):\n        pass\n\n\nclass Contract:\n    def test_adds(self):\n        self.assertEqual(add(2, 3), 5)\n\n\nclass TestV1(Other, Contract, unittest.TestCase):\n    pass\n\n\nclass TestV2(Contract, unittest.TestCase):\n    pass\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_c.py": HDR
    + "\n\nclass Other:\n    def test_zero(self):\n        pass\n\n\nclass Contract:\n    def test_adds(self):\n        self.assertEqual(add(2, 3), 5)\n\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base via TestV2\n\n\nclass TestV1(Other, Contract, unittest.TestCase):\n    pass\n\n\nclass TestV2(Contract, unittest.TestCase):\n    pass\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["Contract.test_zero is green on base"]
EXPECT_NOT = []
