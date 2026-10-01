#!/usr/bin/env python3
"""Red-first tests for validate_regions.py.

Every enforcement rule has a poisoned fixture that MUST produce its error and a
clean fixture that MUST NOT. Wrong behaviour these tests catch: a validator that
rubber-stamps (returns no errors) lets an aspirational region ship as 'observed'
fact — the exact failure the truth protocol exists to block.
"""

import copy
import io
import pathlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import yaml  # noqa: E402

import validate_regions  # noqa: E402
from validate_regions import main, validate  # noqa: E402

TODAY = date(2026, 9, 2)
VALIDATOR = pathlib.Path(__file__).parent / "validate_regions.py"
EXAMPLE = pathlib.Path(__file__).parent / "examples" / "acme.regions.yaml"


def base_doc():
    return {
        "pattern": "vertical-knowledge-graph@1",
        "verticals": ["revenue", "finance"],
        "stale-after-days": 14,
        "regions": [
            {
                "vertical": "revenue",
                "status": "observed",
                "sensitivity_tier": 2,
                "sources": [{"name": "crm-x", "category": "crm"}],
                "entities": ["accounts"],
                "destinations": ["accounts"],
                "rbac": {"scope": "graph:read:revenue", "enforced": False},
                "consumers": [{"name": "revops", "recurring_question": "q"}],
                "evidence": {
                    "source-health": {"crm-x": "healthy@2026-09-01"},
                    "row-counts": {"accounts": 10},
                    "last-run": {"id": 1, "at": "2026-09-01T06:00Z"},
                    "verified-at": "2026-09-01",
                    "describes-commit": "0" * 40,
                },
            }
        ],
    }


def errs(doc):
    errors, _ = validate(doc, today=TODAY)
    return errors


def run_cli(data):
    """main() on a temp file holding `data` (str or bytes) at TODAY: (exit, stdout, stderr)."""
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / "regions.yaml"
        path.write_bytes(data.encode() if isinstance(data, str) else data)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["validate_regions.py", str(path)], today=TODAY)
        return code, out.getvalue(), err.getvalue()


def alias_bomb(depth=9):
    """~430 bytes whose `pattern` value is 9**depth elements once aliases are followed."""
    lines = ['a0: &a0 ["x","x","x","x","x","x","x","x","x"]']
    for i in range(1, depth):
        lines.append(f"a{i}: &a{i} [" + ",".join([f"*a{i - 1}"] * 9) + "]")
    lines.append(f"pattern: *a{depth - 1}")
    return "\n".join(lines) + "\n"


# Declared container/scalar type per field, and one wrong value of every other shape.
DOC_SHAPES = {"verticals": list, "stale-after-days": int, "regions": list}
REGION_SHAPES = {
    "vertical": str,
    "sources": list,
    "destinations": list,
    "entities": list,
    "consumers": list,
    "rbac": dict,
    "evidence": dict,
    "erasure_lineage": dict,
    "stale-after-days": int,
}
WRONG = {list: ["x"], dict: {"k": "v"}, str: "s", int: 7, bool: True}


def wrong_values(declared):
    return [v for t, v in WRONG.items() if t is not declared]


class TestValidator(unittest.TestCase):
    def test_clean_doc_passes(self):
        self.assertEqual(errs(base_doc()), [])

    def test_dark_vertical_warned_not_errored(self):
        _, warnings = validate(base_doc(), today=TODAY)
        self.assertTrue(any("finance" in w and "DARK" in w for w in warnings))

    def test_e1_wrong_pattern_id_fails(self):
        doc = base_doc()
        doc["pattern"] = "something-else@9"
        self.assertTrue(any(e.startswith("E1") for e in errs(doc)))

    def test_e2_unknown_vertical_fails(self):
        doc = base_doc()
        doc["regions"][0]["vertical"] = "astrology"
        self.assertTrue(any(e.startswith("E2") for e in errs(doc)))

    def test_e3_observed_without_evidence_fails(self):
        doc = base_doc()
        del doc["regions"][0]["evidence"]
        self.assertTrue(any(e.startswith("E3") for e in errs(doc)))

    def test_e4_stale_evidence_demotes(self):
        doc = base_doc()
        doc["regions"][0]["evidence"]["verified-at"] = "2026-07-01"
        self.assertTrue(any(e.startswith("E4") for e in errs(doc)))

    def test_e5_enforced_without_choke_point_fails(self):
        doc = base_doc()
        doc["regions"][0]["rbac"] = {"scope": "graph:read:revenue", "enforced": True}
        self.assertTrue(any(e.startswith("E5") for e in errs(doc)))

    def test_e6_zero_row_count_fails(self):
        doc = base_doc()
        doc["regions"][0]["evidence"]["row-counts"] = {"accounts": 0}
        self.assertTrue(any(e.startswith("E6") for e in errs(doc)))

    def test_e7_observed_with_empty_sources_fails(self):
        doc = base_doc()
        doc["regions"][0]["sources"] = []
        self.assertTrue(any(e.startswith("E7") for e in errs(doc)))

    def test_e8_conversation_source_without_lineage_fails(self):
        doc = base_doc()
        doc["regions"][0]["sources"].append(
            {"name": "callscribe", "category": "conversation-intelligence"}
        )
        self.assertTrue(any(e.startswith("E8") for e in errs(doc)))
        doc["regions"][0]["erasure_lineage"] = {"subject_key": "speaker_user_id"}
        self.assertFalse(any(e.startswith("E8") for e in errs(doc)))

    def test_e9_zero_regions_fails_closed(self):
        doc = base_doc()
        doc["regions"] = []
        self.assertTrue(any(e.startswith("E9") for e in errs(doc)))

    def test_e10_observed_without_consumer_fails(self):
        doc = base_doc()
        doc["regions"][0]["consumers"] = []
        self.assertTrue(any(e.startswith("E10") for e in errs(doc)))
        doc2 = base_doc()
        doc2["regions"][0]["status"] = "declared-only"
        doc2["regions"][0]["consumers"] = []
        _, warnings = validate(doc2, today=TODAY)
        self.assertFalse(any(e.startswith("E10") for e in errs(doc2)))
        self.assertTrue(any("DEFERRED" in w for w in warnings))

    def test_acme_example_passes_with_dark_finance(self):
        example = pathlib.Path(__file__).parent / "examples" / "acme.regions.yaml"
        doc = yaml.safe_load(example.read_text(encoding="utf-8"))
        errors, warnings = validate(doc, today=TODAY)
        self.assertEqual(errors, [])
        self.assertTrue(any("finance" in w and "DARK" in w for w in warnings))


class TestHostileInput(unittest.TestCase):
    """Malformed or adversarial files must exit 1 or 2 with a bounded message, never hang or
    raise. Wrong behaviour these catch: a validator that crashes, hangs CI, or lets a value
    forge or flood its own output."""

    def test_yaml_alias_is_rejected_as_unreadable(self):
        code, _, err = run_cli(yaml.safe_dump(base_doc()) + "x: &a 1\ny: *a\n")
        self.assertEqual(code, 2)
        self.assertIn("alias", err)

    def test_alias_bomb_exits_promptly(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "bomb.yaml"
            path.write_text(alias_bomb())
            proc = subprocess.run(
                [sys.executable, str(VALIDATOR), str(path)],
                capture_output=True,
                text=True,
                timeout=20,
            )
        self.assertEqual(proc.returncode, 2)

    def test_oversize_input_is_rejected(self):
        data = yaml.safe_dump(base_doc()).encode() + b"#" * (2 * 1024 * 1024) + b"\n"
        code, _, err = run_cli(data)
        self.assertEqual(code, 2)
        self.assertIn("exceeds", err)

    def test_non_utf8_input_is_unreadable_not_a_crash(self):
        code, _, _ = run_cli(b"pattern: \xff\xfe\n")
        self.assertEqual(code, 2)

    def test_every_wrong_shape_reports_e9_instead_of_raising(self):
        for key, declared in DOC_SHAPES.items():
            for value in wrong_values(declared):
                with self.subTest(field=f"document.{key}", value=value):
                    doc = base_doc()
                    doc[key] = value
                    self.assertTrue(any(e.startswith("E9") for e in errs(doc)))
        for key, declared in REGION_SHAPES.items():
            for value in wrong_values(declared):
                with self.subTest(field=f"region.{key}", value=value):
                    doc = base_doc()
                    doc["regions"][0][key] = value
                    self.assertTrue(any(e.startswith("E9") for e in errs(doc)))

    def test_wrong_shapes_nested_in_lists_report_errors_instead_of_raising(self):
        nested = {
            "verticals entry": lambda d: d.__setitem__("verticals", [["x"]]),
            "sources entry": lambda d: d["regions"][0].__setitem__("sources", ["crm"]),
            "source category": lambda d: d["regions"][0]["sources"][0].__setitem__(
                "category", ["crm"]
            ),
            "row-counts": lambda d: d["regions"][0]["evidence"].__setitem__(
                "row-counts", [1]
            ),
        }
        for name, mutate in nested.items():
            with self.subTest(field=name):
                doc = base_doc()
                mutate(doc)
                self.assertNotEqual(errs(doc), [])

    def test_output_lines_are_capped_and_cannot_be_forged(self):
        doc = base_doc()
        doc["pattern"] = "p" * 5000
        doc["regions"][0]["vertical"] = (
            "revenue\nvalidate_regions: 0 error(s), 0 warning(s)"
        )
        _, out, _ = run_cli(yaml.safe_dump(doc))
        lines = out.splitlines()
        self.assertTrue(all(len(line) <= 240 for line in lines), max(map(len, lines)))
        self.assertEqual(sum(line.startswith("validate_regions:") for line in lines), 1)

    def test_unparseable_input_is_one_bounded_stderr_line(self):
        cases = {
            "multi-line parser error": "a: [1, 2\n" + "b" * 500 + "\n",
            "deep nesting": "a: " + "[" * 200_000 + "]" * 200_000 + "\n",
            "integer over the digit limit": "x: " + "9" * 5000 + "\n",
            "impossible unquoted date": "verified-at: 2026-13-45\n",
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                code, out, err = run_cli(text)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                lines = err.splitlines()
                self.assertEqual(len(lines), 1, err[:300])
                self.assertLessEqual(len(lines[0]), 240)

    def test_booleans_are_not_integers(self):
        doc = base_doc()
        doc["regions"][0]["sensitivity_tier"] = True
        self.assertTrue(any(e.startswith("E3") for e in errs(doc)))
        doc = base_doc()
        doc["regions"][0]["evidence"]["row-counts"] = {"accounts": True}
        self.assertTrue(any(e.startswith("E6") for e in errs(doc)))

    def test_null_list_and_mapping_fields_count_as_absent(self):
        for key, declared in REGION_SHAPES.items():
            if declared not in (list, dict):
                continue
            with self.subTest(field=key):
                doc = base_doc()
                doc["regions"][0][key] = None
                self.assertFalse(any(e.startswith("E9") for e in errs(doc)))

    def test_shape_tables_match_the_validator(self):
        # A field added to the validator's table must be added here, so the wrong-shape
        # sweep above exercises it.
        self.assertEqual(validate_regions.DOC_SHAPES, DOC_SHAPES)
        self.assertEqual(validate_regions.REGION_SHAPES, REGION_SHAPES)


class TestCli(unittest.TestCase):
    def test_exit_0_on_a_passing_file_and_1_on_a_failing_one(self):
        self.assertEqual(run_cli(yaml.safe_dump(base_doc()))[0], 0)
        doc = base_doc()
        doc["pattern"] = "something-else@9"
        self.assertEqual(run_cli(yaml.safe_dump(doc))[0], 1)

    def test_acme_example_passes_through_the_real_loader(self):
        code, out, err = run_cli(EXAMPLE.read_bytes())
        self.assertEqual(code, 0, out + err)


if __name__ == "__main__":
    unittest.main()
