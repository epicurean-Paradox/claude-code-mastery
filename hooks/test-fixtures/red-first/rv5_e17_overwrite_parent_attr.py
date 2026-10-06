# Base pkg exposes `pkg.settings` (an object); the PR turns it into a subpackage pkg/settings/.
# A new test imports the new submodule; the stub module overwrites the real pkg.settings attribute.
BASE = {
    "pkg/__init__.py": "class _S:\n    debug = False\n\nsettings = _S()\n\ndef add(a, b):\n    return a + b\n",
    "tests/test_pkg.py": "import unittest\nimport pkg\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(pkg.add(1, 0), 1)\n",
}
PR = {
    "pkg/__init__.py": "from .settings import settings\n\ndef add(a, b):\n    return a + b\n",
    "pkg/settings/__init__.py": "class _S:\n    debug = False\n\nsettings = _S()\n",
    "pkg/settings/loader.py": "def load():\n    return {}\n",
    "tests/test_pkg.py": "import unittest\nimport pkg\nfrom pkg.settings.loader import load\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(pkg.add(1, 0), 1)\n\n    def test_load(self):\n        self.assertEqual(load(), {})\n\n    def test_debug_off(self):\n        self.assertFalse(pkg.settings.debug)   # green on base\n",
}

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_debug_off is green on base"]
EXPECT_NOT = ["RED-FIRST:TestAdd.test_load"]
