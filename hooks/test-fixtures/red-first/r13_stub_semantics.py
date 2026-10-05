# Sanity of the stub against the shapes named in the brief: each verdict is listed below.
HDR = """\
import pathlib, sys, unittest
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
from lib import add, notify
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef process():\n    return 1\n",
    "tests/test_lib.py": "import pathlib, sys, unittest\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\nfrom lib import add\n\nclass TestA(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n",
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\ndef notify():\n    pass\n\ndef process():\n    notify()\n    return 1\n",
    "tests/test_lib.py": HDR
    + """
class TestA(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
    @unittest.skipIf(notify is None, "no notify")
    def test_skipif_is_none_green(self):
        self.assertEqual(add(0, 0), 0)
    @mock.patch.object(lib, "notify")
    def test_process_notifies(self, m):
        lib.process()
        m.assert_called_once()
    def test_default_arg_green(self, f=notify):
        self.assertEqual(add(0, 0), 0)
    def test_isinstance(self):
        self.assertFalse(isinstance(1, notify))
    def test_eq(self):
        self.assertNotEqual(notify, None)
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
# test_isinstance passes a function as isinstance's class argument: it errors at HEAD too.
EXPECT = [
    "TestA.test_skipif_is_none_green is green on base",
    "TestA.test_default_arg_green is green on base",
    "TestA.test_isinstance does not pass at HEAD (error: TypeError)",
    "TestA.test_eq: error on base (missing on base: lib.notify)",
    "TestA.test_process_notifies: error on base (AttributeError)",
]
EXPECT_NOT = ["RED-FIRST:TestA.test_eq", "RED-FIRST:TestA.test_process_notifies"]
