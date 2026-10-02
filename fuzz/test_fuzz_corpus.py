"""Regression replay of fuzz/corpus/<target>/ (LESSONS Lesson 29).

Every committed seed runs through the same target function the coverage-guided driver uses,
so what the fuzzer found stays found. Each seed pins its outcome: the exit code for the two
CLIs (plus the reason, for the ledger lint; the rule tags, for the council lint), the flag
count for evidence-audit. Runs without
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
    # exit code of validate_regions.main at the suite's pinned date
    "regions": {
        "valid-acme": 0,
        "stale-evidence": 1,
        "yaml-alias": 2,
    },
    # (exit code, text the output must contain): the reason is pinned, not only the code
    "ledger": {
        "valid-mini": (0, "OK"),
        "valid-small": (0, "OK"),
        "missing-row": (1, "has NO ledger row"),
        "orphan-row": (1, "orphan row"),
        "id-gap": (1, "lesson-id gap"),
        # found by the fuzzer: read_text() raised UnicodeDecodeError
        "crash-not-utf8": (1, "not UTF-8"),
        # found by the fuzzer: an 82-byte file whose 46-digit lesson id made the gap
        # check build range(1, 7.7e45) and run out of memory
        "oom-lesson-id-range": (1, "more than 4 digits"),
        "crash-lesson-id-5000-digits": (1, "more than 4 digits"),
        # an oversize id in LEDGER.md is reported on LEDGER.md, not LESSONS.md
        "id-oversize-in-ledger": (1, "LEDGER.md:ID:"),
    },
    # flag count of evidence-audit's scan()
    "evidence": {
        "valid-mini": 1,
        # found by the fuzzer: open(encoding="utf-8").readlines() raised. Its garbage
        # also breaks the JSON line, so 0; the next seed proves the scan still runs.
        "crash-not-utf8": 0,
        # undecodable bytes inside an otherwise valid line: still scanned, still flags
        "not-utf8-inside-text": 1,
        # found by the fuzzer: a JSONL line that parses to a non-object reached ev.get()
        "crash-json-not-object": 0,
        # json.loads raises RecursionError, not JSONDecodeError, on deep nesting
        "crash-json-deep-nesting": 0,
        # the same class enumerated by hand: every field turns() reads, in a wrong shape.
        # A malformed block is skipped; a well-formed block beside it is still scanned.
        "shape-message-string": 0,
        "shape-content-blocks-mixed": 0,
        "shape-tool-input-list": 0,
        "shape-tool-command-int": 0,
        "shape-tool-name-list": 1,
    },
    # (exit code, rule tags) of agent-council-lint; first byte % 3: 0 agent, 1 council, 2 lock
    "council": {
        "valid-agent": (0, set()),
        "valid-council": (0, set()),
        "agent-no-model": (1, {"A2"}),
        "agent-alias": (1, {"A3"}),  # the model line holds *a, not a model
        "council-single-family-no-reason": (1, {"C6", "C7"}),
        "council-refuter-same-family": (1, {"C7"}),
        "council-no-dissent": (1, {"C9"}),
        # first byte 2: the A4 pin lock beside a fixed agent file
        "lock-valid": (0, set()),
        "lock-drift": (1, {"A4"}),
        "lock-escape": (1, {"A4"}),
        # found by the fuzzer: a pinned path with control characters and ':' reached the
        # path field of the output line and broke the path:RULE:message contract
        "crash-lock-path-control-chars": (1, {"A4"}),
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
                    if target == "ledger":
                        (code, output), (want_code, needle) = got, want
                        self.assertEqual(code, want_code, output[:300])
                        self.assertIn(needle, output)
                    else:
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
