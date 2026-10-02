#!/usr/bin/env python3
"""Tests for agent-council-lint.py.

A valid agent and a valid council record must lint clean; each rule has a mutation of
that fixture which must trip exactly that rule. Wrong behaviour these catch: a lint that
passes an un-routed subagent, a single-family council presented as independent, a refuter
on the author's family, or a record with no dissent -- and a lint that fires on the wrong
rule, which would send an adopter to fix the wrong field.
"""

import contextlib
import importlib.util
import io
import pathlib
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("acl", HERE / "agent-council-lint.py")
acl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(acl)

AGENT = """---
name: reviewer
description: Reviews a diff.
model: sonnet
---
You review diffs.
"""

COUNCIL_NAME = "2026-10-02-vpc-peering.md"
COUNCIL_META = {
    "topic": "vpc-peering",
    "date": "2026-10-02",
    "author_model": "claude-opus-5-5",
    "refuter": "security-iam",
    "lenses": (
        "  - {lens: reliability-observability, model: claude-sonnet-5-5}\n"
        "  - {lens: security-iam, model: gemini-2.5-pro}\n"
        "  - {lens: iac-delivery, model: claude-opus-5-5}\n"
        "  - {lens: cost-operations, model: claude-haiku-4-5}"
    ),
    "single_family_reason": '""',
    "verdict": "approve-with-conditions",
}
COUNCIL_BODY = """
## Disagreements
Security wanted the peering route table scoped to two subnets; reliability accepted.

## Rejected
A transit gateway: more cost than two VPCs justify.
"""


def council(meta=None, body=COUNCIL_BODY, drop=()):
    fields = dict(COUNCIL_META, **(meta or {}))
    lines = []
    for key, value in fields.items():
        if key in drop:
            continue
        lines.append(f"{key}:\n{value}" if key == "lenses" else f"{key}: {value}")
    return "---\n" + "\n".join(lines) + "\n---\n" + body


class Repo:
    """A throwaway adopter repo with optional agent and council files."""

    def __init__(self, agents=None, councils=None):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        for name, text in (agents or {}).items():
            p = self.root / ".claude" / "agents" / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(text.encode() if isinstance(text, str) else text)
        for name, text in (councils or {}).items():
            p = self.root / "docs" / "council" / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(text.encode() if isinstance(text, str) else text)

    def lint(self, *flags):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = acl.main(["agent-council-lint.py", *flags, str(self.root)])
        self._tmp.cleanup()
        lines = out.getvalue().splitlines()
        return code, {line.split(":", 2)[1] for line in lines}, lines


def lint(agents=None, councils=None, *flags):
    return Repo(agents, councils).lint(*flags)


class TestValidFixture(unittest.TestCase):
    def test_valid_agent_and_council_lint_clean(self):
        code, rules, lines = lint({"reviewer.md": AGENT}, {COUNCIL_NAME: council()})
        self.assertEqual((code, lines), (0, []))

    def test_single_family_council_with_a_reason_lints_clean(self):
        meta = {
            "lenses": COUNCIL_META["lenses"].replace(
                "gemini-2.5-pro", "claude-sonnet-5-5"
            ),
            "single_family_reason": '"only one provider is approved for this data"',
        }
        code, _, lines = lint(None, {COUNCIL_NAME: council(meta)})
        self.assertEqual((code, lines), (0, []))

    def test_hosted_inference_ids_resolve_to_their_provider(self):
        self.assertEqual(acl.model_family("eu.anthropic.claude-opus-5"), "anthropic")
        self.assertEqual(
            acl.model_family("eu.mistral.pixtral-large-2502-v1:0"), "mistral"
        )
        self.assertEqual(acl.model_family("us.meta.llama3-70b"), "meta")
        self.assertIsNone(acl.model_family("inherit"))
        self.assertIsNone(acl.model_family("some-new-model"))


class TestAgentRules(unittest.TestCase):
    def cases(self):
        return {
            "A1": "no frontmatter here\n",
            "A2": AGENT.replace("model: sonnet\n", ""),
            "A3": AGENT.replace("model: sonnet", "model: gpt-5"),
        }

    def test_each_agent_rule_fires_alone(self):
        for rule, text in self.cases().items():
            with self.subTest(rule=rule):
                code, rules, _ = lint({"a.md": text}, None)
                self.assertEqual((code, rules), (1, {rule}))

    def test_wrong_shapes_in_agent_frontmatter_are_errors_not_crashes(self):
        bad = {
            "list model": AGENT.replace("model: sonnet", "model: [sonnet]"),
            "alias": "---\nx: &a 1\nmodel: *a\n---\n",
            "not a mapping": "---\n- model\n---\n",
            "not utf-8": b"---\nmodel: \xff\n---\n",
            "deep nesting": "---\nmodel: " + "[" * 5000 + "]" * 5000 + "\n---\n",
        }
        for name, text in bad.items():
            with self.subTest(case=name):
                code, rules, _ = lint({"a.md": text}, None)
                self.assertEqual(code, 1)
                self.assertTrue(rules <= {"A1", "A2", "A3"}, rules)

    def test_an_alias_on_the_model_line_is_refused(self):
        code, rules, _ = lint({"a.md": "---\nm: &a sonnet\nmodel: *a\n---\n"}, None)
        self.assertEqual((code, rules), (1, {"A3"}))


class TestCouncilRules(unittest.TestCase):
    def cases(self):
        one_family = COUNCIL_META["lenses"].replace(
            "gemini-2.5-pro", "claude-sonnet-5-5"
        )
        return {
            "C1": ("vpc-peering.md", council()),
            "C2": (COUNCIL_NAME, council(drop=("verdict",))),
            "C3": (COUNCIL_NAME, council({"date": "2026-10-01"})),
            "C4": (
                COUNCIL_NAME,
                council(
                    {
                        "lenses": COUNCIL_META["lenses"].replace(
                            "cost-operations", "cost"
                        )
                    }
                ),
            ),
            "C5": (
                COUNCIL_NAME,
                council(
                    {
                        "lenses": COUNCIL_META["lenses"].replace(
                            "claude-haiku-4-5", "inherit"
                        )
                    }
                ),
            ),
            # one family is C6, and then the refuter shares it too: C7 (asserted as a pair)
            "C7": (COUNCIL_NAME, council({"refuter": "iac-delivery"})),
            "C8": (COUNCIL_NAME, council({"verdict": "maybe"})),
            "C9": (
                COUNCIL_NAME,
                council(body="\n## Disagreements\n\n## Rejected\nNone.\n"),
            ),
        } | {"C6+C7": (COUNCIL_NAME, council({"lenses": one_family}))}

    def test_each_council_rule_fires_alone(self):
        for rule, (name, text) in self.cases().items():
            with self.subTest(rule=rule):
                code, rules, _ = lint(None, {name: text})
                self.assertEqual((code, rules), (1, set(rule.split("+"))))

    def test_missing_dissent_section_is_c9(self):
        code, rules, _ = lint(
            None, {COUNCIL_NAME: council(body="\n## Rejected\nNone.\n")}
        )
        self.assertEqual((code, rules), (1, {"C9"}))

    def test_wrong_shapes_in_council_frontmatter_are_errors_not_crashes(self):
        bad = {
            "lenses a string": council({"lenses": '"four of them"'}),
            "lens entry a list": council(
                {"lenses": "  - [security-iam, gemini-2.5-pro]"}
            ),
            "refuter a list": council({"refuter": "[security-iam]"}),
            "date an int": council({"date": "20261002"}),
            "verdict a mapping": council({"verdict": "{a: 1}"}),
            "author_model null": council({"author_model": "null"}),
        }
        for name, text in bad.items():
            with self.subTest(case=name):
                code, rules, _ = lint(None, {COUNCIL_NAME: text})
                self.assertEqual(code, 1)
                self.assertTrue(rules, "an error must be reported")


class TestReviewFindings(unittest.TestCase):
    """Shapes found in review of the first cut, each seen red before its fix."""

    def test_crlf_council_lints_clean(self):
        code, _, lines = lint(None, {COUNCIL_NAME: council().replace("\n", "\r\n")})
        self.assertEqual((code, lines), (0, []))

    def test_byte_order_mark_is_not_a_missing_frontmatter(self):
        bom = "\ufeff"
        code, _, lines = lint({"a.md": bom + AGENT}, {COUNCIL_NAME: bom + council()})
        self.assertEqual((code, lines), (0, []))

    def test_agent_fields_claude_code_tolerates_do_not_fail_the_lint(self):
        # an unquoted ": " in description is invalid strict YAML but a working agent file
        text = AGENT.replace("Reviews a diff.", "Use when: reviewing a diff")
        self.assertEqual(lint({"a.md": text}, None)[:2], (0, set()))

    def test_an_inline_comment_on_the_model_line_is_a3(self):
        # recorded breaking agent launch: the comment is read as part of the model name
        text = AGENT.replace("model: sonnet", "model: inherit  # explicit")
        self.assertEqual(lint({"a.md": text}, None)[:2], (1, {"A3"}))

    def test_a_model_declared_twice_is_a3(self):
        # two valid values: only the duplicate check can catch it
        text = AGENT.replace("model: sonnet", "model: sonnet\nmodel: opus")
        self.assertEqual(lint({"a.md": text}, None)[:2], (1, {"A3"}))

    def test_anthropic_model_forms_are_accepted(self):
        for model in (
            "sonnet[1m]",
            "opusplan",
            "fable",
            '"claude-opus-5"',
            "anthropic.claude-sonnet-4-5-20250929-v1:0",
            "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "claude-sonnet-4-5@20250929",
        ):
            with self.subTest(model=model):
                text = AGENT.replace("model: sonnet", f"model: {model}")
                self.assertEqual(lint({"a.md": text}, None)[:2], (0, set()))

    def test_a_trailing_escape_or_non_claude_model_is_a3(self):
        for model in ('"claude-opus-5\\n"', "claude-opus-5 extra", "gemini-2.5-pro"):
            with self.subTest(model=model):
                text = AGENT.replace("model: sonnet", f"model: {model}")
                self.assertEqual(lint({"a.md": text}, None)[:2], (1, {"A3"}))

    def test_family_prefixes_need_a_boundary(self):
        cases = {
            "o3rd-party-thing": None,
            "o10": "openai",
            "o3-mini": "openai",
            "llamaindex-agent": None,
            "llama-3.3-70b": "meta",
            "mixtral-8x7b": "mistral",
            "devstral-small": "mistral",
            "deepseek-r1": "deepseek",
            "google/gemini-2.5-pro": "google",
            "models/gemini-2.5-pro": "google",
            "openai/gpt-oss-120b": "openai",
            "au.anthropic.claude-sonnet-4-5": "anthropic",
            "grok-4": None,
        }
        for model, family in cases.items():
            with self.subTest(model=model):
                self.assertEqual(acl.model_family(model), family)

    def test_dissent_sections_cannot_be_satisfied_vacuously(self):
        fenced = "\n```md\n## Disagreements\nx\n\n## Rejected\ny\n```\n"
        bodies = {
            "only inside a code fence": fenced,
            "only subheadings": "\n## Disagreements\n### Security\n\n## Rejected\n### Cost\n",
            "placeholder": "\n## Disagreements\nTODO\n\n## Rejected\nNone.\n",
            "html comment": "\n## Disagreements\n<!-- later -->\n\n## Rejected\nx y\n",
            "zero-width": "\n## Disagreements\n\u200b\n\n## Rejected\nx y\n",
            "duplicate heading": COUNCIL_BODY + "\n## Disagreements\nmore\n",
        }
        for name, body in bodies.items():
            with self.subTest(case=name):
                code, rules, _ = lint(None, {COUNCIL_NAME: council(body=body)})
                self.assertEqual((code, rules), (1, {"C9"}))

    def test_required_fields_must_be_filled_and_dates_real(self):
        code, rules, _ = lint(None, {COUNCIL_NAME: council({"topic": "null"})})
        self.assertEqual((code, rules), (1, {"C2"}))
        bad_day = council({"date": "2026-02-30"})
        code, rules, _ = lint(None, {"2026-02-30-vpc.md": bad_day})
        self.assertEqual(code, 1)
        self.assertIn("C1", rules)

    def test_a_reason_does_not_waive_c7_when_two_families_are_present(self):
        meta = {"refuter": "iac-delivery", "single_family_reason": '"n/a"'}
        self.assertEqual(lint(None, {COUNCIL_NAME: council(meta)})[:2], (1, {"C7"}))

    def test_duplicate_lens_names_are_c4(self):
        lenses = (
            COUNCIL_META["lenses"]
            + "\n  - {lens: security-iam, model: claude-opus-5-5}"
        )
        self.assertEqual(
            lint(None, {COUNCIL_NAME: council({"lenses": lenses})})[:2], (1, {"C4"})
        )

    def test_nested_councils_are_linted_and_readmes_skipped(self):
        repo = Repo(
            {"README.md": "# agents\n", "_template.md": "x"},
            {
                "infra/2026-10-02-vpc.md": council().replace(
                    "2026-10-02", "2026-10-01", 1
                ),
                "README.md": "# councils\n",
                "_template.md": "x",
            },
        )
        code, rules, lines = repo.lint()
        self.assertEqual((code, rules), (1, {"C3"}), lines)


class TestSingleRecordMode(unittest.TestCase):
    def run_one(self, text, name=COUNCIL_NAME):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / name
            path.write_text(text)
            out = io.StringIO()
            with (
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                code = acl.main(["agent-council-lint.py", "--council", str(path)])
            return code, {line.split(":", 2)[1] for line in out.getvalue().splitlines()}

    def test_a_valid_record_passes_and_no_zero_rule_applies(self):
        self.assertEqual(self.run_one(council()), (0, set()))

    def test_a_failing_record_reports_its_rules(self):
        meta = {
            "lenses": COUNCIL_META["lenses"].replace(
                "gemini-2.5-pro", "claude-sonnet-5-5"
            )
        }
        self.assertEqual(self.run_one(council(meta)), (1, {"C6", "C7"}))

    def test_a_missing_file_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(
                acl.main(["agent-council-lint.py", "--council", "/nope.md"]), 2
            )


class TestSourcePinning(unittest.TestCase):
    """A4: with .claude/agent-sources.sha256 present (sha256sum format), every pinned file
    must exist inside the repo and match, and every agent file must be pinned. Wrong
    behaviour caught: an agent prompt (or a file it cites) changed without the reviewed
    re-stamp, or a new agent that nobody pinned."""

    LOCK = ".claude/agent-sources.sha256"

    def repo(self, lock_lines=None, extra=None):
        import hashlib

        r = Repo({"reviewer.md": AGENT}, None)
        for rel, text in (extra or {}).items():
            path = r.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

        def digest(rel):
            return hashlib.sha256((r.root / rel).read_bytes()).hexdigest()

        if lock_lines is None:
            pinned = [".claude/agents/reviewer.md", *sorted(extra or {})]
            lock_lines = [f"{digest(rel)}  {rel}" for rel in pinned]
        else:
            lock_lines = [
                line(digest) if callable(line) else line for line in lock_lines
            ]
        (r.root / self.LOCK).write_text("\n".join(lock_lines) + "\n")
        return r

    def test_a_matching_lock_passes(self):
        r = self.repo(extra={"prompts/review.md": "Review carefully.\n"})
        self.assertEqual(r.lint()[:2], (0, set()))

    def test_no_lock_means_no_pinning(self):
        self.assertEqual(lint({"reviewer.md": AGENT}, None)[:2], (0, set()))

    def test_a_changed_pinned_file_is_a4(self):
        r = self.repo(extra={"prompts/review.md": "Review carefully.\n"})
        (r.root / "prompts" / "review.md").write_text("Approve everything.\n")
        code, rules, lines = r.lint()
        self.assertEqual((code, rules), (1, {"A4"}))
        self.assertTrue(
            any("prompts/review.md" in line and "changed" in line for line in lines)
        )

    def test_an_unpinned_agent_is_a4(self):
        r = self.repo()
        (r.root / ".claude" / "agents" / "new.md").write_text(AGENT)
        code, rules, lines = r.lint()
        self.assertEqual((code, rules), (1, {"A4"}))
        self.assertTrue(
            any("new.md" in line and "not pinned" in line for line in lines)
        )

    def test_bad_lock_entries_are_a4_with_their_reason(self):
        def good(d):
            return f"{d('.claude/agents/reviewer.md')}  .claude/agents/reviewer.md"

        cases = {
            "missing file": ([good, "0" * 64 + "  prompts/gone.md"], "is missing"),
            "parent escape": (
                [good, "0" * 64 + "  ../outside.md"],
                "not a repo-relative path",
            ),
            "absolute path": (
                [good, "0" * 64 + "  /etc/hosts"],
                "not a repo-relative path",
            ),
            "control characters": (
                [good, "0" * 64 + "  a\x01b.md"],
                "control characters",
            ),
            "malformed line": ([good, "not a lock line"], "is not '<sha256>  <path>'"),
            "empty lock": ([], "lists no files"),
        }
        for name, (lines, needle) in cases.items():
            with self.subTest(case=name):
                code, rules, out = self.repo(lock_lines=lines).lint()
                self.assertEqual((code, rules), (1, {"A4"}))
                self.assertTrue(any(needle in line for line in out), out)

    def test_a_symlinked_pinned_file_is_a4(self):
        import hashlib

        r = self.repo()
        outside = pathlib.Path(tempfile.mkdtemp()) / "x.md"
        outside.write_text("outside\n")
        (r.root / "prompts").mkdir()
        (r.root / "prompts" / "x.md").symlink_to(outside)
        digest = hashlib.sha256(outside.read_bytes()).hexdigest()
        with open(r.root / self.LOCK, "a") as fh:
            fh.write(f"{digest}  prompts/x.md\n")
        code, rules, out = r.lint()
        self.assertEqual((code, rules), (1, {"A4"}))
        self.assertTrue(any("symlink" in line for line in out), out)

    def test_sha256sum_variants_are_accepted(self):
        # binary-mode marker, ./ prefix, uppercase hex, CRLF line endings
        r = self.repo(
            lock_lines=[
                lambda d: (
                    f"{d('.claude/agents/reviewer.md').upper()} *./.claude/agents/reviewer.md\r"
                )
            ]
        )
        self.assertEqual(r.lint()[:2], (0, set()))


class TestZeroAndContract(unittest.TestCase):
    def test_an_empty_repo_fails_closed(self):
        self.assertEqual(lint(None, None)[:2], (1, {"ZERO"}))

    def test_allow_empty_passes_an_empty_repo(self):
        self.assertEqual(lint(None, None, "--allow-empty")[:2], (0, set()))

    def test_allow_empty_still_lints_what_is_there(self):
        code, rules, _ = lint({"a.md": "no frontmatter\n"}, None, "--allow-empty")
        self.assertEqual((code, rules), (1, {"A1"}))

    def test_output_lines_are_bounded_and_single(self):
        meta = {"refuter": '"' + "x" * 5000 + '\\nagent-council-lint: 0 error(s)"'}
        code, _, lines = lint(None, {COUNCIL_NAME: council(meta)})
        self.assertEqual(code, 1)
        self.assertTrue(all(len(line) <= acl.MAX_LINE for line in lines))
        self.assertTrue(all(line.count(":") >= 2 for line in lines))

    def test_a_control_character_in_a_filename_cannot_split_a_line(self):
        code, _, lines = lint(None, {"bad\nname.md": council()})
        self.assertEqual(code, 1)
        self.assertTrue(all(line.startswith("docs/council/") for line in lines), lines)

    def test_usage_error_is_exit_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(acl.main(["agent-council-lint.py", "--bogus"]), 2)


if __name__ == "__main__":
    unittest.main()
