# Every subtest skips at HEAD (no backend on the runner); nothing asserts anywhere. The
# skips are recorded under the _SubTest objects, the case then "succeeds": green at HEAD,
# so no pin is needed, while a plain self.skipTest() would need one.
HDR = """\
import pathlib, shutil, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lib
"""
BASE = {
    "lib.py": "BACKENDS = ()\n",
    "tests/test_lib.py": HDR
    + "\nclass TestB(unittest.TestCase):\n    def test_x(self):\n        pass\n",
}
PR = {
    "lib.py": "BACKENDS = ('pg-not-installed', 'mysql-not-installed')\n\ndef connect(name):\n    raise RuntimeError('broken')\n",
    "tests/test_lib.py": HDR
    + """
class TestB(unittest.TestCase):
    def test_x(self):
        pass
    def test_connect_each_backend(self):
        self.assertTrue(lib.BACKENDS)
        for name in lib.BACKENDS:
            with self.subTest(name):
                if not shutil.which(name):
                    self.skipTest(f"{name} not on this runner")
                self.assertTrue(lib.connect(name))
""",
}
AFTER = [
    "python3 -m unittest discover -v -s tests 2>&1 | grep -E '^test_|^Ran|^OK|^FAILED'"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["does not pass at HEAD (skipped)"]
EXPECT_NOT = []
