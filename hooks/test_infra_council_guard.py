#!/usr/bin/env python3
"""Tests for infra-council-guard.sh, run against throwaway git repos.

Wrong behaviour these catch: an infra mutation that runs with no council record, a stale
one, a dirty working tree, or a record that fails agent-council-lint (single model family,
refuter on the author's family, no real dissent); a read-only command that gets blocked
(which trains people to disable the gate); and a configured path the guard ignores.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
GUARD = HERE / "infra-council-guard.sh"
sys.path.insert(0, str(HERE))
from test_agent_council_lint import COUNCIL_META, COUNCIL_NAME, council  # noqa: E402

T1, T2, T3 = "2026-10-01T10:00:00", "2026-10-02T10:00:00", "2026-10-03T10:00:00"
ONE_FAMILY = COUNCIL_META["lenses"].replace("gemini-2.5-pro", "claude-sonnet-5-5")


class Repo:
    def __init__(self, git=True):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name).resolve()
        if git:
            self.git("init", "-q")
            self.commit("infra/main.tf", 'resource "null_resource" "x" {}\n', T1)

    def git(self, *args, date=None):
        env = dict(
            os.environ,
            GIT_AUTHOR_NAME="t",
            GIT_AUTHOR_EMAIL="t@example.invalid",
            GIT_COMMITTER_NAME="t",
            GIT_COMMITTER_EMAIL="t@example.invalid",
        )
        if date:
            env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            env=env,
        )

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self, rel, text, date):
        self.write(rel, text)
        self.git("add", rel)
        self.git("commit", "-q", "-m", rel, date=date)

    def run(self, command, env=None, process_cwd=None, tool="Bash"):
        """(blocked, reason) for one tool call through the hook."""
        payload = json.dumps(
            {
                "tool_name": tool,
                "tool_input": {"command": command},
                "cwd": str(self.root),
            }
        )
        full_env = dict(os.environ)
        # the guard runs `python3` for the lint; make it the interpreter running the tests
        full_env["PATH"] = f"{pathlib.Path(sys.executable).parent}:{full_env['PATH']}"
        full_env.update(env or {})
        r = subprocess.run(
            ["bash", str(GUARD)],
            input=payload,
            capture_output=True,
            text=True,
            cwd=process_cwd or self.root,
            env=full_env,
            timeout=60,
        )
        self.last_stderr = r.stderr
        assert r.returncode == 0, r.stderr
        if not r.stdout.strip():
            return False, ""
        out = json.loads(r.stdout)
        assert out["decision"] == "block", out
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny", out
        return True, out["reason"]

    def close(self):
        self._tmp.cleanup()


class GuardCase(unittest.TestCase):
    def repo(self, git=True):
        r = Repo(git)
        self.addCleanup(r.close)
        return r

    def assertBlocked(self, result, needle=""):
        blocked, reason = result
        self.assertTrue(blocked, "expected a block")
        self.assertIn(needle, reason)

    def assertAllowed(self, result):
        blocked, reason = result
        self.assertFalse(blocked, reason[:400])


class TestExistingBehaviour(GuardCase):
    def test_read_only_commands_pass(self):
        r = self.repo()
        for cmd in (
            "terraform plan",
            "terraform -chdir=infra validate",
            "aws ec2 describe-instances",
            "aws cloudwatch set-alarm-state --alarm-name x --state-value OK --state-reason t",
        ):
            with self.subTest(cmd=cmd):
                self.assertAllowed(r.run(cmd))

    def test_another_tool_passes(self):
        self.assertAllowed(self.repo().run("terraform apply", tool="Write"))

    def test_apply_without_a_council_is_blocked_in_every_spelling(self):
        r = self.repo()
        for cmd in (
            "terraform apply",
            "terraform -chdir=infra apply -auto-approve",
            "terraform plan && terraform apply",
            "tofu destroy",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked(r.run(cmd), "No council record")

    def test_apply_with_a_fresh_valid_council_passes(self):
        r = self.repo()
        r.commit(f"docs/council/{COUNCIL_NAME}", council(), T2)
        self.assertAllowed(r.run("terraform apply"))

    def test_a_council_older_than_the_infra_is_blocked(self):
        r = self.repo()
        r.commit(f"docs/council/{COUNCIL_NAME}", council(), T2)
        r.commit("infra/main.tf", 'resource "null_resource" "y" {}\n', T3)
        blocked, reason = r.run("terraform apply")
        self.assertBlocked((blocked, reason), "PRE-DATES")
        self.assertIn("2026-10-03", reason)  # a date, not raw epoch seconds (GNU date)

    def test_uncommitted_infra_is_blocked(self):
        r = self.repo()
        r.commit(f"docs/council/{COUNCIL_NAME}", council(), T2)
        r.write("infra/main.tf", 'resource "null_resource" "dirty" {}\n')
        self.assertBlocked(r.run("terraform apply"), "uncommitted changes")

    def test_outside_a_git_repo_is_blocked(self):
        self.assertBlocked(
            self.repo(git=False).run("terraform apply"), "not inside a git"
        )

    def test_raw_aws_mutation_needs_a_committed_fresh_record(self):
        r = self.repo()
        cmd = "aws budgets update-budget --account-id 1 --new-budget x"
        self.assertBlocked(r.run(cmd), "No COUNCIL_ACK")
        r.write(f"docs/council/{COUNCIL_NAME}", council())
        ack = f"COUNCIL_ACK=docs/council/{COUNCIL_NAME} {cmd}"
        self.assertBlocked(r.run(ack), "not committed")
        r.git("add", "docs")
        r.git("commit", "-q", "-m", "council", date=T2)
        self.assertAllowed(r.run(ack))
        self.assertBlocked(r.run(f"COUNCIL_ACK=infra/main.tf {cmd}"), "docs/council")


class TestLintAtApply(GuardCase):
    def test_a_fresh_record_that_fails_the_lint_blocks_apply(self):
        r = self.repo()
        r.commit(f"docs/council/{COUNCIL_NAME}", council({"lenses": ONE_FAMILY}), T2)
        self.assertBlocked(r.run("terraform apply"), "C6")

    def test_council_ack_naming_a_record_that_fails_the_lint_is_blocked(self):
        r = self.repo()
        bad = council(body="\n## Disagreements\nNone.\n\n## Rejected\nNone.\n")
        r.commit(f"docs/council/{COUNCIL_NAME}", bad, T2)
        cmd = f"COUNCIL_ACK=docs/council/{COUNCIL_NAME} aws budgets update-budget --x y"
        self.assertBlocked(r.run(cmd), "C9")

    def test_only_the_newest_record_is_linted(self):
        r = self.repo()
        r.commit("docs/council/2026-09-01-legacy.md", "# an old free-form record\n", T1)
        r.commit(f"docs/council/{COUNCIL_NAME}", council(), T2)
        self.assertAllowed(r.run("terraform apply"))

    def test_lint_off_skips_the_record_check(self):
        r = self.repo()
        r.commit(f"docs/council/{COUNCIL_NAME}", council({"lenses": ONE_FAMILY}), T2)
        self.assertAllowed(r.run("terraform apply", env={"INFRA_COUNCIL_LINT": "off"}))

    def test_a_missing_linter_blocks_instead_of_skipping(self):
        r = self.repo()
        r.commit(f"docs/council/{COUNCIL_NAME}", council(), T2)
        env = {"INFRA_COUNCIL_LINT": str(r.root / "nope" / "agent-council-lint.py")}
        self.assertBlocked(r.run("terraform apply", env=env), "agent-council-lint")


class TestConfiguration(GuardCase):
    def test_custom_infra_paths_are_what_freshness_is_measured_against(self):
        r = self.repo()
        r.commit(f"docs/council/{COUNCIL_NAME}", council(), T2)
        r.commit("deploy/stack.yaml", "kind: Stack\n", T3)
        self.assertAllowed(r.run("terraform apply"))
        env = {"INFRA_COUNCIL_PATHS": "deploy/ infra/"}
        self.assertBlocked(r.run("terraform apply", env=env), "PRE-DATES")

    def test_custom_infra_paths_count_for_a_dirty_tree(self):
        r = self.repo()
        r.commit(f"docs/council/{COUNCIL_NAME}", council(), T2)
        r.write("deploy/stack.yaml", "kind: Dirty\n")
        r.git("add", "deploy/stack.yaml")
        env = {"INFRA_COUNCIL_PATHS": "deploy/"}
        self.assertBlocked(r.run("terraform apply", env=env), "uncommitted changes")

    def test_custom_council_dir(self):
        r = self.repo()
        r.commit(f"reviews/council/{COUNCIL_NAME}", council(), T2)
        env = {"INFRA_COUNCIL_DIR": "reviews/council"}
        self.assertAllowed(r.run("terraform apply", env=env))
        self.assertBlocked(r.run("terraform apply"), "No council record")

    def test_the_payload_cwd_locates_the_repo(self):
        r = self.repo()
        r.commit(f"docs/council/{COUNCIL_NAME}", council(), T2)
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        self.assertAllowed(r.run("terraform apply", process_cwd=elsewhere.name))


if __name__ == "__main__":
    unittest.main()
