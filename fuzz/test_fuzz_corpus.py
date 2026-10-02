"""Regression replay of fuzz/corpus/<target>/ (LESSONS Lesson 29).

Every committed seed runs through the same target function the coverage-guided driver uses,
so what the fuzzer found stays found. Each seed pins its outcome: the exit code for the two
CLIs, the flag count (or None for "any count, no crash") for evidence-audit. Runs without
atheris.

Wrong behaviour this catches: a parser that crashes, breaks its output contract, or changes
its verdict on an input a previous fuzz run (or a hand-written seed) already established.
"""

import pathlib
import sys
import unittest

FUZZ = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(FUZZ))
import targets  # noqa: E402

CORPUS = FUZZ / "corpus"

EXPECTED = {
    "regions": {
        "valid-acme": 0,
    },
    "ledger": {
        "valid-mini": 0,
        "valid-repo": 0,
        # found by the fuzzer: read_text() raised UnicodeDecodeError
        "crash-not-utf8": 1,
    },
    "evidence": {
        "valid-mini": 1,
        # found by the fuzzer: open(encoding="utf-8").readlines() raised
        "crash-not-utf8": None,
        # found by the fuzzer: a JSONL line that parses to a non-object reached ev.get()
        "crash-json-not-object": 0,
        # the same class enumerated by hand: every field turns() reads, in a wrong shape.
        # A malformed block is skipped; a well-formed block beside it is still scanned.
        "shape-message-string": 0,
        "shape-content-blocks-mixed": 0,
        "shape-tool-input-list": 0,
        "shape-tool-command-int": 0,
        "shape-tool-name-list": 1,
    },
}


class TestCorpus(unittest.TestCase):
    def test_corpus_and_expectations_name_the_same_seeds(self):
        # An unpinned seed is dead weight; a pinned seed that is missing is a lost regression.
        for target, seeds in EXPECTED.items():
            with self.subTest(target=target):
                on_disk = {p.name for p in (CORPUS / target).iterdir() if p.is_file()}
                self.assertEqual(on_disk, set(seeds))

    def test_every_seed_keeps_its_outcome(self):
        for target, seeds in EXPECTED.items():
            for seed, want in seeds.items():
                with self.subTest(target=target, seed=seed):
                    got = targets.TARGETS[target]((CORPUS / target / seed).read_bytes())
                    if want is not None:
                        self.assertEqual(got, want)

    def test_hook_fixtures_keep_their_verdicts(self):
        # hooks/test-fixtures doubles as the evidence corpus' hand-written seeds.
        fixtures = targets.REPO / "hooks" / "test-fixtures"
        for path in sorted(fixtures.glob("*.jsonl")):
            with self.subTest(fixture=path.name):
                flags = targets.run_evidence(path.read_bytes())
                if path.name.startswith("fail_"):
                    self.assertGreater(flags, 0)
                else:
                    self.assertEqual(flags, 0)


if __name__ == "__main__":
    unittest.main()
