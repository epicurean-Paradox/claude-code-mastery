# Escape direction: the PR hoists the lazy import (cleanup) and adds a test of EXISTING
# behaviour. On the base the lazy import runs after the chdir and fails: "error", counted red.
T = """\
import os, tempfile, unittest
import cli

class TestCli(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(tempfile.mkdtemp())
"""
BASE = {
    "cli.py": "def run(cmd):\n    import commands\n    return commands.dispatch(cmd)\n",
    "commands.py": "def dispatch(cmd):\n    return {'version': '1.0'}.get(cmd)\n",
    "tests/test_cli.py": T + "    def test_x(self):\n        pass\n",
}
PR = {
    "cli.py": "import commands\n\ndef run(cmd):\n    return commands.dispatch(cmd)\n",
    "tests/test_cli.py": T
    + "    def test_x(self):\n        pass\n    def test_version(self):\n        self.assertEqual(cli.run('version'), '1.0')   # green on the base\n",
}
AFTER = [
    "git checkout -q HEAD~1 -- cli.py && python3 -m unittest discover -v -s tests 2>&1 | grep -E '^test_|^OK|^FAILED'; git checkout -q HEAD -- ."
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestCli.test_version is green on base"]
EXPECT_NOT = []
