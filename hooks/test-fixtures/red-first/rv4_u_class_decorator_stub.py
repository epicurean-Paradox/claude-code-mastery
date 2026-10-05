# Honest red-first PR: adds lib.override_flags, a class decorator, and a test class that uses
# it. On the base the stub absorbs the decoration and REPLACES the class: "not collected", a
# violation no pin can excuse.
HDR = "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
BASE = {
    "lib.py": "FLAGS = {}\n\n\ndef enabled(name):\n    return False\n",
    "tests/test_lib.py": HDR
    + "import lib\n\n\nclass TestOld(unittest.TestCase):\n    def test_off(self):\n        self.assertFalse(lib.enabled('x'))\n",
}
PR = {
    "lib.py": "FLAGS = {}\n\n\ndef enabled(name):\n    return FLAGS.get(name, False)\n\n\ndef override_flags(**flags):\n    def deco(cls):\n        cls.setUp = lambda self: FLAGS.update(flags)\n        return cls\n    return deco\n",
    "tests/test_lib.py": HDR
    + """import lib
from lib import override_flags


class TestOld(unittest.TestCase):
    def test_off(self):
        self.assertFalse(lib.enabled('y'))


@override_flags(x=True)
class TestOn(unittest.TestCase):
    def test_on(self):
        self.assertTrue(lib.enabled('x'))
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestOn.test_on: red on base"]
EXPECT_NOT = []
