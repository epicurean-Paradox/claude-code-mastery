HDR = """\
import os, pathlib, shutil, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "def ping(client):\n    return False\n",
    "tests/test_lib.py": HDR
    + "\nclass TestX(unittest.TestCase):\n    def test_x(self):\n        pass\n",
}
PR = {
    "lib.py": "def ping(client):\n    return client.test_connection()\n",
    "tests/test_lib.py": HDR
    + """
class FakeClient:  # a stub, not a TestCase: its API has a test_connection method
    def test_connection(self):
        return True

class TestX(unittest.TestCase):
    def test_x(self):
        pass
    def test_ping_uses_client(self):
        self.assertTrue(lib.ping(FakeClient()))
    @unittest.skipUnless(shutil.which("terraform-not-on-this-runner"), "needs terraform")
    def test_ping_real(self):  # red-first: pins only runs where terraform is installed
        self.assertTrue(lib.ping(FakeClient()))
""",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["FakeClient.test_connection: not a test"]
EXPECT_NOT = []
