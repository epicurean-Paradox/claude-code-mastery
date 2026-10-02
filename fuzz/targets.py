"""Fuzz targets over the three parsers that sit in this repo's gates (LESSONS Lesson 29).

Each run_* takes raw fuzz bytes, drives one parser through the entry point CI and the hooks
use, and asserts that parser's output contract. An AssertionError is a contract break; any
other exception is a crash. Both are findings: reproduce, add the input to
fuzz/corpus/<target>/ with its expectation in fuzz/test_fuzz_corpus.py, see it red, then fix.

Stdlib + PyYAML only and importable without atheris, so the corpus replay runs anywhere; the
coverage-guided driver is fuzz/fuzz.py.
"""

import contextlib
import importlib.util
import io
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(name, REPO / relpath)
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: atheris.instrument_all() skips functions whose module is
    # not in sys.modules, which left all three parsers uninstrumented (blind fuzzing).
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


regions = _load(
    "validate_regions", "patterns/vertical-knowledge-graph/validate_regions.py"
)
ledger_lint = _load("lesson_ledger_lint", "hooks/lesson-ledger-lint.py")
evidence = _load("evidence_audit", "hooks/evidence-audit.py")

TODAY = date(
    2026, 9, 2
)  # the regions suite's pinned date; a fuzz run never reads the clock
EVIDENCE_KINDS = {"causal", "absence", "state-chain"}
_TMP = Path(tempfile.mkdtemp(prefix="ccm-fuzz-"))


def _quiet(fn, *args, **kwargs):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(*args, **kwargs)
    return code, out.getvalue() + err.getvalue()


def run_regions(data):
    """validate_regions.main on a file holding `data`. Returns the exit code."""
    path = _TMP / "regions.yaml"
    path.write_bytes(data)
    code, output = _quiet(regions.main, ["validate_regions.py", str(path)], today=TODAY)
    assert code in (0, 1, 2), f"exit code {code!r}"
    for line in output.splitlines():
        assert len(line) <= regions.MAX_LINE, f"{len(line)}-char output line"
    assert "\r" not in output, "unescaped carriage return in output"
    return code


def run_ledger(data):
    """lesson-ledger-lint.main with LESSONS.md / LEDGER.md replaced by `data`, split at the
    first NUL byte (no NUL: all of it is LESSONS.md, LEDGER.md is empty). Gate files still
    resolve against the real repo. Returns (exit code, output)."""
    lessons, _, ledger = data.partition(b"\x00")
    (_TMP / "LESSONS.md").write_bytes(lessons)
    (_TMP / "LEDGER.md").write_bytes(ledger)
    saved = ledger_lint.LESSONS, ledger_lint.LEDGER
    ledger_lint.LESSONS, ledger_lint.LEDGER = _TMP / "LESSONS.md", _TMP / "LEDGER.md"
    try:
        code, output = _quiet(ledger_lint.main)
    finally:
        ledger_lint.LESSONS, ledger_lint.LEDGER = saved
    assert code in (0, 1), f"exit code {code!r}"
    return code, output


def run_evidence(data):
    """evidence-audit's scan() over a transcript holding `data`. Returns the flag count."""
    path = _TMP / "transcript.jsonl"
    path.write_bytes(data)
    flags = evidence.scan(str(path))
    for turn, kind, snippet in flags:
        assert isinstance(turn, int), f"turn {turn!r}"
        assert kind in EVIDENCE_KINDS, f"kind {kind!r}"
        assert isinstance(snippet, str) and len(snippet) <= 160, "snippet unbounded"
    return len(flags)


TARGETS = {"regions": run_regions, "ledger": run_ledger, "evidence": run_evidence}
PARSERS = (regions, ledger_lint, evidence)
