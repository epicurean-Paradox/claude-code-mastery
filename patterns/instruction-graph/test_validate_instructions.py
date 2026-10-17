"""Red-first tests for the instruction-graph reference validator.

unittest (run by `python3 -m unittest discover` in CI). Every poison mutates a
known-valid instrument and asserts the validator errors, so the error is caused
by the poison and not a broken baseline (test_valid_instrument_passes proves the
baseline). The Acme example must pass the config-invariant checks.

The reference validator checks shape only; resolving an enforcement reference to
a real symbol (the binding half) is an implementation's own test, documented in
the pattern -- not reproduced here against a fictional example.
"""

import pathlib
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from validate_instructions import (  # noqa: E402
    MAX_FRONTMATTER_BYTES,
    _fmt,
    enforcement_problem,
    load_dir,
    load_instrument,
    split_frontmatter,
    validate,
)

HERE = pathlib.Path(__file__).parent
EXAMPLES = HERE / "examples" / "acme-instruments"
TODAY = date(2026, 10, 17)


def valid(**over):
    fm = {
        "id": "sample-rule",
        "title": "A sample rule",
        "layer": "project",
        "type": "rule",
        "status": "active",
        "enforcement": {"kind": "hook", "ref": "hooks/x.sh", "state": "declared"},
    }
    fm.update(over)
    return fm


def run(*fms):
    return validate([(f"p{i}", fm) for i, fm in enumerate(fms)], TODAY)


def codes(errors):
    return {e.split(":", 1)[0] for e in errors}


class Baseline(unittest.TestCase):
    def test_valid_instrument_passes(self):
        errors, warnings = run(valid())
        self.assertEqual(errors, [])
        self.assertEqual({w.split(":", 1)[0] for w in warnings}, {"W1"})


class Schema(unittest.TestCase):
    def test_missing_required_key(self):
        for key in ("id", "title", "layer", "type", "status"):
            fm = valid()
            del fm[key]
            errors, _ = run(fm)
            self.assertTrue(codes(errors) & {"I1", "I6"}, key)

    def test_unknown_layer(self):
        self.assertIn("I2", codes(run(valid(layer="galaxy"))[0]))

    def test_unknown_type(self):
        self.assertIn("I3", codes(run(valid(type="edict"))[0]))

    def test_unknown_status(self):
        self.assertIn("I4", codes(run(valid(status="maybe"))[0]))

    def test_superseded_needs_superseded_by(self):
        self.assertIn("I4", codes(run(valid(status="superseded"))[0]))

    def test_withdrawn_needs_reason(self):
        self.assertIn("I4", codes(run(valid(status="withdrawn"))[0]))

    def test_additional_properties_rejected(self):
        self.assertIn("I1", codes(run(valid(linkz={"refines": ["x"]}))[0]))

    def test_non_string_type_does_not_crash(self):
        self.assertIn("I3", codes(run(valid(type=["rule"]))[0]))

    def test_non_string_status_does_not_crash(self):
        self.assertIn("I4", codes(run(valid(status={"v": "active"}))[0]))


class Enforcement(unittest.TestCase):
    def test_rule_without_enforcement(self):
        fm = valid()
        del fm["enforcement"]
        self.assertIn("I5", codes(run(fm)[0]))

    def test_kind_none_requires_absent(self):
        self.assertIn(
            "I5", codes(run(valid(enforcement={"kind": "none", "state": "live"}))[0])
        )

    def test_kind_none_absent_ok(self):
        self.assertEqual(
            run(valid(enforcement={"kind": "none", "state": "absent"}))[0], []
        )

    def test_non_none_requires_ref(self):
        self.assertIn(
            "I5",
            codes(
                run(valid(enforcement={"kind": "test", "ref": " ", "state": "live"}))[0]
            ),
        )

    def test_non_string_kind_does_not_crash(self):
        self.assertIn(
            "I5",
            codes(
                run(valid(enforcement={"kind": ["hook"], "ref": "x", "state": "live"}))[
                    0
                ]
            ),
        )

    def test_non_mapping_enforcement(self):
        self.assertIsNotNone(enforcement_problem("hooks/x.sh"))

    def test_narrative_needs_no_enforcement(self):
        fm = valid(type="narrative")
        del fm["enforcement"]
        self.assertEqual(run(fm)[0], [])


class Ids(unittest.TestCase):
    def test_duplicate_id(self):
        self.assertIn("I6", codes(run(valid(), valid())[0]))

    def test_non_identifier_id(self):
        self.assertIn("I6", codes(run(valid(id="not valid!!"))[0]))


class Links(unittest.TestCase):
    def test_dangling_target(self):
        self.assertIn("I7", codes(run(valid(links={"refines": ["nope"]}))[0]))

    def test_unknown_verb(self):
        self.assertIn(
            "I7", codes(run(valid(links={"inspired_by": ["sample-rule"]}))[0])
        )

    def test_non_list_targets(self):
        self.assertIn("I7", codes(run(valid(links={"refines": "sample-rule"}))[0]))

    def test_non_string_member(self):
        self.assertIn("I7", codes(run(valid(id="rule-a", links={"refines": [123]}))[0]))

    def test_resolvable_link_ok(self):
        a = valid(id="rule-a", links={"refines": ["rule-b"]})
        b = valid(id="rule-b")
        self.assertEqual(run(a, b)[0], [])


class Graph(unittest.TestCase):
    def test_cycle_rejected(self):
        a = valid(id="rule-a", links={"refines": ["rule-b"]})
        b = valid(id="rule-b", links={"refines": ["rule-a"]})
        self.assertIn("I8", codes(run(a, b)[0]))

    def test_same_layer_conflict_without_supersedes(self):
        a = valid(id="rule-a", links={"conflicts_with": ["rule-b"]})
        b = valid(id="rule-b")
        self.assertIn("I8", codes(run(a, b)[0]))

    def test_conflict_resolved_by_supersedes_ok(self):
        a = valid(
            id="rule-a", links={"conflicts_with": ["rule-b"], "supersedes": ["rule-b"]}
        )
        b = valid(id="rule-b")
        self.assertEqual(run(a, b)[0], [])

    def test_enforces_cycle_is_exempt(self):
        a = valid(id="rule-a", links={"enforces": ["rule-b"]})
        b = valid(id="rule-b", links={"enforced_by": ["rule-a"]})
        self.assertNotIn("I8", codes(run(a, b)[0]))

    def test_zero_instruments_fail_closed(self):
        self.assertIn("I9", codes(validate([], TODAY)[0]))


class Loader(unittest.TestCase):
    def _write(self, text):
        p = pathlib.Path(tempfile.mkdtemp()) / "x.md"
        p.write_text(text, encoding="utf-8")
        return p

    def test_split_frontmatter(self):
        self.assertEqual(split_frontmatter("---\na: 1\n---\nbody"), "a: 1")
        self.assertIsNone(split_frontmatter("no frontmatter"))
        self.assertIsNone(split_frontmatter("---\nunterminated\nbody"))

    def test_no_frontmatter_rejected(self):
        fm, problem = load_instrument(self._write("# body only\n"))
        self.assertIsNone(fm)
        self.assertTrue(problem)

    def test_oversized_frontmatter_rejected(self):
        body = "k: " + "v" * (MAX_FRONTMATTER_BYTES + 10)
        fm, problem = load_instrument(self._write(f"---\n{body}\n---\n"))
        self.assertIsNone(fm)
        self.assertIn("bytes", problem)

    def test_alias_refused(self):
        fm, problem = load_instrument(self._write("---\na: &x [1]\nb: *x\n---\n"))
        self.assertIsNone(fm)
        self.assertIn("alias", problem.lower())

    def test_flow_sequence_alias_refused(self):
        fm, problem = load_instrument(self._write("---\nk: [&a 1, *a, *a]\n---\n"))
        self.assertIsNone(fm)
        self.assertIn("alias", problem.lower())

    def test_quoted_asterisk_allowed(self):
        fm, problem = load_instrument(
            self._write(
                '---\nid: ab\ntitle: "A & B, see *.yaml"\nlayer: project\n'
                "type: narrative\nstatus: active\n---\n"
            )
        )
        self.assertIsNone(problem)
        self.assertEqual(fm["id"], "ab")


class OutputContract(unittest.TestCase):
    def test_fmt_bounds_and_escapes(self):
        self.assertLessEqual(len(_fmt("x" * 500)), 240)
        self.assertNotIn("\n", _fmt("line1\nline2"))
        self.assertNotIn("\t", _fmt("a\tb"))


class Example(unittest.TestCase):
    def test_acme_example_passes(self):
        instruments, load_errors = load_dir(EXAMPLES)
        self.assertEqual(load_errors, [])
        self.assertTrue(instruments, "no example instruments found")
        errors, _ = validate(instruments, TODAY)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
