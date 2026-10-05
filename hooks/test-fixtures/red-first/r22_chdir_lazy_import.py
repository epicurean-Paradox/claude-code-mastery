# Suite runs as `python -m unittest discover -s tests` from the root (so the root is on
# sys.path as an ABSOLUTE path). The CLI test chdirs into a temp dir; the CLI lazily imports
# its subcommand module. Under `python -c` the root is on sys.path only as '' (the cwd), so
# after the chdir the lazy import fails.
T = """\
import os, tempfile, unittest
import cli

class TestCli(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(tempfile.mkdtemp())
    def test_version(self):
        self.assertEqual(cli.run("version"), "1.0")
"""
BASE = {
    "cli.py": "def run(cmd):\n    import commands\n    return commands.dispatch(cmd)\n",
    "commands.py": "def dispatch(cmd):\n    return {'version': '1.0'}.get(cmd)\n",
    "tests/test_cli.py": T,
}
PR = {
    "commands.py": "def dispatch(cmd):\n    return {'version': '1.0', 'help': 'usage: cli'}.get(cmd)\n",
    "tests/test_cli.py": T
    + "    def test_help(self):\n        self.assertEqual(cli.run('help'), 'usage: cli')\n",
}
AFTER = [
    "python3 -m unittest discover -v -s tests 2>&1 | grep -E '^test_|^Ran|^OK|^FAILED'"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 0
EXPECT = ["TestCli.test_help: red on base"]
EXPECT_NOT = []
