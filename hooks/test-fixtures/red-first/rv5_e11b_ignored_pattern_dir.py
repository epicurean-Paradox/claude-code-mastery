# Generated modules matched by a FILE pattern, inside an untracked directory that holds only them.
BASE = {
    ".gitignore": "*_pb2.py\n",
    "pkg/__init__.py": "",
    "pkg/proto/msg_pb2.py": "NAME = 'msg'\n",
    "pkg/core.py": "from pkg.proto.msg_pb2 import NAME\n\ndef add(a, b):\n    return a - b\n",
    "tests/test_core.py": "import unittest\nfrom pkg.core import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n",
}
PR = {
    "pkg/core.py": "from pkg.proto.msg_pb2 import NAME\n\ndef add(a, b):\n    return a + b\n",
    "tests/test_core.py": "import unittest\nfrom pkg.core import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(add(1, 0), 1)\n\n    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)   # green on base\n",
}
AFTER = [
    "git ls-files -z --others --ignored --exclude-standard --directory | tr '\\0' '\\n'"
]

# Intended outcome: the exit code, and lines the output must or must not hold.
EXIT = 1
EXPECT = ["TestAdd.test_zero is green on base"]
EXPECT_NOT = []
