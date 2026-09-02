#!/usr/bin/env python3
"""Red-first tests for validate_regions.py.

Every enforcement rule has a poisoned fixture that MUST produce its error and a
clean fixture that MUST NOT. Wrong behaviour these tests catch: a validator that
rubber-stamps (returns no errors) lets an aspirational region ship as 'observed'
fact — the exact failure the truth protocol exists to block.
"""

import copy
import pathlib
import sys
import unittest
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import yaml  # noqa: E402

from validate_regions import validate  # noqa: E402

TODAY = date(2026, 9, 2)


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


if __name__ == "__main__":
    unittest.main()
