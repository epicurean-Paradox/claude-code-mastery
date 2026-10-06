# Honest red-first tests using fixture machinery; each should be red on base, green at HEAD.
HDR = """\
import asyncio, pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib

STATE = {}

def setUpModule():
    STATE["dir"] = tempfile.mkdtemp()

def tearDownModule():
    STATE.clear()
"""
TAIL = """
if __name__ == "__main__":
    unittest.main()
"""
OLD = """
class TestAdd(unittest.TestCase):
    def test_x(self):
        pass
"""
NEW = """
class TestAdd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calls = []
        cls.addClassCleanup(cls.calls.clear)
    def setUp(self):
        self.addCleanup(lambda: None)
    def test_x(self):
        pass
    def test_adds(self):
        self.assertTrue(STATE["dir"])
        self.assertEqual(lib.add(2, 3), 5)

class TestAsync(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.loop_ok = asyncio.get_running_loop() is not None
    async def test_aadd(self):
        self.assertTrue(self.loop_ok)
        self.assertEqual(await lib.aadd(2, 3), 5)
"""
BASE = {
    "lib.py": "def add(a, b):\n    return a - b\n\nasync def aadd(a, b):\n    return a - b\n",
    "tests/test_lib.py": HDR + OLD + TAIL,
}
PR = {
    "lib.py": "def add(a, b):\n    return a + b\n\nasync def aadd(a, b):\n    return a + b\n",
    "tests/test_lib.py": HDR + NEW + TAIL,
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestAdd.test_adds: red on base", "TestAsync.test_aadd: red on base"]
EXPECT_NOT = []
