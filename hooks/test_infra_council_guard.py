#!/usr/bin/env python3
"""Tests for infra-council-guard.sh, run against throwaway git repos.

Wrong behaviour these catch: an infra mutation that runs with no council record, a stale
one, a dirty working tree, or a record that fails agent-council-lint (single model family,
refuter on the author's family, no real dissent); every bypass found in review (a harmless
AWS call or a COUNCIL_ACK in the same command, a README touch that makes a stale record
look fresh, two records in one commit, a forged commit date, a shallow clone, a cd into
another repo, an uncommitted edit to the record); a hook that crashes open instead of
blocking; and a read-only command that gets blocked, which trains people to disable the
gate. Every block assertion names a reason unique to the branch that should fire.
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
GUARD = HERE / "infra-council-guard.sh"
sys.path.insert(0, str(HERE))
from test_agent_council_lint import COUNCIL_META, COUNCIL_NAME, council  # noqa: E402

T1, T2, T3, T4 = (f"2026-10-0{d}T10:00:00" for d in (1, 2, 3, 4))
ONE_FAMILY = COUNCIL_META["lenses"].replace("gemini-2.5-pro", "claude-sonnet-5-5")
RECORD = f"docs/council/{COUNCIL_NAME}"
APPLY = (
    "terraform " + "apply"
)  # the tool name and verb, kept apart in source on purpose
RAW_AWS = "aws budgets update-budget --account-id 1 --new-budget x"


class Repo:
    def __init__(self, git=True):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name).resolve()
        if git:
            self.git("init", "-q")
            self.commit("infra/main.tf", 'resource "null_resource" "x" {}\n', T1)

    def git(self, *args, date=None, committer_date=None):
        env = dict(
            os.environ,
            GIT_AUTHOR_NAME="t",
            GIT_AUTHOR_EMAIL="t@example.invalid",
            GIT_COMMITTER_NAME="t",
            GIT_COMMITTER_EMAIL="t@example.invalid",
        )
        if date:
            env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=committer_date or date)
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

    def commit(self, rel, text, date, committer_date=None):
        self.write(rel, text)
        self.git("add", rel)
        self.git("commit", "-q", "-m", rel, date=date, committer_date=committer_date)

    def run(self, command, env=None, process_cwd=None, tool="Bash", path=None):
        """(blocked, reason) for one tool call. A deny JSON is a block; so is exit 2, the
        blocking exit a crashing hook must use. Anything else non-zero fails the test."""
        payload = json.dumps(
            {
                "tool_name": tool,
                "tool_input": {"command": command},
                "cwd": str(self.root),
            }
        )
        full_env = dict(os.environ)
        # the guard runs `python3` for the lint; make it the interpreter running the tests
        full_env["PATH"] = (
            path or f"{pathlib.Path(sys.executable).parent}:{full_env['PATH']}"
        )
        full_env.update(env or {})
        r = subprocess.run(
            ["bash", str(GUARD)],
            input=payload,
            capture_output=True,
            text=True,
            cwd=process_cwd or self.root,
            env=full_env,
            timeout=120,
        )
        if r.returncode == 2:
            return True, "EXIT2: " + r.stderr
        assert r.returncode == 0, (r.returncode, r.stderr)
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

    def fresh(self, text=None):
        """A repo whose newest record is valid (or `text`) and committed after the infra."""
        r = self.repo()
        r.commit(RECORD, text or council(), T2)
        return r

    def assertBlocked(self, result, needle):
        blocked, reason = result
        self.assertTrue(blocked, "expected a block")
        self.assertIn(needle, reason)

    def assertAllowed(self, result):
        blocked, reason = result
        self.assertFalse(blocked, reason[:500])


class TestReadOnlyAndOtherTools(GuardCase):
    def test_read_only_commands_pass(self):
        r = self.repo()
        for cmd in (
            "terraform plan -out tfplan",
            "terraform -chdir=infra validate",
            "cd infra && terraform plan",
            "pulumi --stack prod preview",
            "aws ec2 describe-instances --profile p",
            "aws s3 ls s3://bucket",
            "aws cloudwatch set-alarm-state --alarm-name x --state-value OK --state-reason t",
            "aws cloudwatch put-metric-data --namespace n --metric-name m --value 1",
        ):
            with self.subTest(cmd=cmd):
                self.assertAllowed(r.run(cmd))

    def test_another_tool_passes(self):
        self.assertAllowed(self.repo().run(APPLY, tool="Write"))


class TestIacGate(GuardCase):
    def test_no_council_blocks_every_spelling(self):
        r = self.repo()
        for cmd in (
            APPLY,
            "terraform -chdir=infra apply -auto-approve",
            "terraform plan && terraform apply",
            "terraform \\\n  apply",
            "terraform 'apply'",
            "terraform workspace delete prod",
            "terraform force-unlock 1234",
            "tofu destroy",
            "terragrunt run-all apply",
            "pulumi --stack prod up",
            "pulumi -s prod up --yes",
            "cdk --profile p deploy",
            "aws --profile prod cloudformation deploy --stack-name s --template-file t",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked(r.run(cmd), "No council record")

    def test_a_fresh_valid_record_passes(self):
        self.assertAllowed(self.fresh().run(APPLY))

    def test_a_record_older_than_the_infra_is_blocked(self):
        r = self.fresh()
        r.commit("infra/main.tf", 'resource "null_resource" "y" {}\n', T3)
        self.assertBlocked(r.run(APPLY), "PRE-DATES")

    def test_touching_another_council_file_does_not_refresh_a_stale_record(self):
        for other in (
            "docs/council/README.md",
            "docs/council/_template.md",
            "docs/council/notes.txt",
        ):
            with self.subTest(other=other):
                r = self.fresh()
                r.commit("infra/main.tf", 'resource "null_resource" "y" {}\n', T3)
                r.commit(other, "touched\n", T4)
                self.assertBlocked(r.run(APPLY), "PRE-DATES")

    def test_a_forged_commit_date_does_not_make_infra_look_older(self):
        r = self.fresh()
        r.commit(
            "infra/main.tf", 'resource "null_resource" "y" {}\n', T3, committer_date=T1
        )
        self.assertBlocked(r.run(APPLY), "PRE-DATES")

    def test_uncommitted_infra_is_blocked(self):
        r = self.fresh()
        r.write("infra/main.tf", 'resource "null_resource" "dirty" {}\n')
        self.assertBlocked(r.run(APPLY), "uncommitted changes")

    def test_a_dirty_tfvars_file_counts_by_default(self):
        r = self.fresh()
        r.write("prod.tfvars", 'size = "big"\n')
        self.assertBlocked(
            r.run(APPLY + " -var-file=prod.tfvars"), "uncommitted changes"
        )

    def test_a_serverless_config_committed_after_the_record_is_stale(self):
        r = self.fresh()
        r.commit("serverless.yml", "service: x\n", T3)
        self.assertBlocked(r.run("serverless deploy"), "PRE-DATES")

    def test_thousands_of_untracked_infra_files_still_block(self):
        r = self.fresh()
        for i in range(4000):
            (r.root / "infra" / f"gen{i}.tf").write_text("")
        self.assertBlocked(r.run(APPLY), "uncommitted changes")

    def test_outside_a_git_repo_is_blocked(self):
        self.assertBlocked(self.repo(git=False).run(APPLY), "not inside a git")

    def test_a_shallow_clone_is_blocked(self):
        src = self.fresh()
        src.commit("infra/main.tf", 'resource "null_resource" "y" {}\n', T3)
        dst = self.repo(git=False)
        subprocess.run(
            [
                "git",
                "clone",
                "-q",
                "--depth",
                "1",
                f"file://{src.root}",
                str(dst.root / "c"),
            ],
            check=True,
            capture_output=True,
        )
        dst.root = dst.root / "c"
        self.assertBlocked(dst.run(APPLY), "shallow")

    def test_the_payload_cwd_locates_the_repo(self):
        r = self.fresh()
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        self.assertAllowed(r.run(APPLY, process_cwd=elsewhere.name))

    def test_changing_into_another_repo_is_blocked(self):
        r = self.fresh()
        other = self.repo()
        for cmd in (
            f"cd {other.root} && {APPLY}",
            f"terraform -chdir={other.root}/infra apply",
            f"cd ~ && {APPLY}",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked(r.run(cmd), "outside the session repository")


class TestRecordLint(GuardCase):
    def test_a_fresh_record_that_fails_the_lint_blocks(self):
        self.assertBlocked(self.fresh(council({"lenses": ONE_FAMILY})).run(APPLY), "C6")

    def test_every_record_in_the_newest_commit_is_linted(self):
        r = self.repo()
        r.write(
            "docs/council/2026-10-02-aaa-ok.md",
            council().replace("vpc-peering", "aaa-ok"),
        )
        bad = council({"lenses": ONE_FAMILY, "topic": "zzz-bad"})
        r.write("docs/council/2026-10-02-zzz-bad.md", bad)
        r.git("add", "docs")
        r.git("commit", "-q", "-m", "two records", date=T2)
        self.assertBlocked(r.run(APPLY), "zzz-bad")

    def test_the_committed_record_is_linted_not_the_working_copy(self):
        r = self.fresh(council({"lenses": ONE_FAMILY}))
        r.write(RECORD, council())  # valid, but never committed
        self.assertBlocked(r.run(APPLY), "C6")

    def test_a_committed_symlink_record_is_blocked(self):
        r = self.repo()
        target = r.root.parent / f"{r.root.name}-outside.md"
        target.write_text(council())
        self.addCleanup(target.unlink)
        (r.root / "docs" / "council").mkdir(parents=True)
        (r.root / RECORD).symlink_to(target)
        r.git("add", "docs")
        r.git("commit", "-q", "-m", "symlink", date=T2)
        self.assertBlocked(r.run(APPLY), "symlink")

    def test_records_under_an_underscore_directory_are_not_records(self):
        r = self.fresh()
        r.commit("docs/council/_templates/record.md", "# fill me in\n", T3)
        self.assertAllowed(r.run(APPLY))

    def test_a_record_deleted_later_is_not_the_newest(self):
        r = self.fresh()
        r.commit(
            "docs/council/2026-10-03-later.md",
            council().replace("2026-10-02", "2026-10-03"),
            T3,
        )
        r.git("rm", "-q", "docs/council/2026-10-03-later.md")
        r.git("commit", "-q", "-m", "drop", date=T4)
        self.assertAllowed(r.run(APPLY))

    def test_only_the_newest_record_is_linted(self):
        r = self.repo()
        r.commit("docs/council/2026-09-01-legacy.md", "# an old free-form record\n", T1)
        r.commit(RECORD, council(), T2)
        self.assertAllowed(r.run(APPLY))

    def test_lint_off_skips_the_record_check(self):
        r = self.fresh(council({"lenses": ONE_FAMILY}))
        self.assertAllowed(r.run(APPLY, env={"INFRA_COUNCIL_LINT": "off"}))

    def test_a_missing_linter_blocks_instead_of_skipping(self):
        r = self.fresh()
        env = {"INFRA_COUNCIL_LINT": str(r.root / "nope" / "agent-council-lint.py")}
        self.assertBlocked(r.run(APPLY, env=env), "agent-council-lint.py not found")


class TestRawAws(GuardCase):
    def test_raw_mutations_need_an_ack(self):
        r = self.repo()
        for cmd in (
            RAW_AWS,
            "/usr/local/bin/aws iam create-role --role-name r",
            "aws iam create-role --role-name r --description put-events",
            "aws ec2 run-instances --image-id x",
            "aws ec2 stop-instances --instance-ids i-1",
            "aws kms schedule-key-deletion --key-id k",
            "aws s3 rb s3://bucket --force",
            "aws s3 rm s3://bucket --recursive",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked(r.run(cmd), "No COUNCIL_ACK")

    def test_a_committed_fresh_linted_ack_passes(self):
        self.assertAllowed(self.fresh().run(f"COUNCIL_ACK={RECORD} {RAW_AWS}"))

    def test_ack_failure_reasons(self):
        r = self.repo()
        r.write(RECORD, council())
        self.assertBlocked(r.run(f"COUNCIL_ACK={RECORD} {RAW_AWS}"), "not committed")
        r.git("add", "docs")
        r.git("commit", "-q", "-m", "record", date=T2)
        r.write(RECORD, council() + "\nedited\n")
        self.assertBlocked(
            r.run(f"COUNCIL_ACK={RECORD} {RAW_AWS}"), "uncommitted edits"
        )
        r.git("checkout", "--", RECORD)
        self.assertBlocked(r.run(f"COUNCIL_ACK=infra/main.tf {RAW_AWS}"), "must name a")
        r.commit("infra/main.tf", 'resource "null_resource" "y" {}\n', T3)
        self.assertBlocked(
            r.run(f"COUNCIL_ACK={RECORD} {RAW_AWS}"),
            "PRE-DATES the newest infra commit",
        )

    def test_an_ack_record_that_fails_the_lint_is_blocked(self):
        bad = council(body="\n## Disagreements\nNone.\n\n## Rejected\nNone.\n")
        self.assertBlocked(self.fresh(bad).run(f"COUNCIL_ACK={RECORD} {RAW_AWS}"), "C9")

    def test_an_ack_from_another_repository_is_blocked(self):
        scratch = self.fresh()
        r = self.repo()
        cmd = f"COUNCIL_ACK={scratch.root / RECORD} {RAW_AWS}"
        self.assertBlocked(r.run(cmd), "same repository")


class TestCompoundCommands(GuardCase):
    def test_a_harmless_aws_call_does_not_excuse_an_iac_mutation(self):
        r = self.repo()
        for cmd in (
            "aws cloudwatch set-alarm-state --alarm-name x --state-value OK --state-reason t; "
            + APPLY,
            APPLY
            + " && aws cloudwatch put-metric-data --namespace n --metric-name m --value 1",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked(r.run(cmd), "No council record")

    def test_an_ack_does_not_excuse_an_iac_mutation_in_the_same_command(self):
        r = self.fresh()
        r.write("infra/main.tf", 'resource "null_resource" "dirty" {}\n')
        cmd = f"COUNCIL_ACK={RECORD} {RAW_AWS}; {APPLY}"
        self.assertBlocked(r.run(cmd), "uncommitted changes")


class TestConfiguration(GuardCase):
    def test_custom_infra_paths_are_what_freshness_is_measured_against(self):
        r = self.fresh()
        r.commit("deploy/stack.yaml", "kind: Stack\n", T3)
        self.assertAllowed(r.run(APPLY))
        env = {"INFRA_COUNCIL_PATHS": "deploy/ infra/"}
        self.assertBlocked(r.run(APPLY, env=env), "PRE-DATES")

    def test_custom_infra_paths_count_for_a_dirty_tree(self):
        r = self.fresh()
        r.write("deploy/stack.yaml", "kind: Dirty\n")
        r.git("add", "deploy/stack.yaml")
        self.assertBlocked(
            r.run(APPLY, env={"INFRA_COUNCIL_PATHS": "deploy/"}), "uncommitted changes"
        )

    def test_custom_council_dir(self):
        r = self.repo()
        r.commit(f"reviews/council/{COUNCIL_NAME}", council(), T2)
        self.assertAllowed(r.run(APPLY, env={"INFRA_COUNCIL_DIR": "reviews/council"}))
        self.assertBlocked(r.run(APPLY), "No council record")

    def test_unusable_configuration_blocks(self):
        r = self.fresh()
        self.assertBlocked(
            r.run(APPLY, env={"INFRA_COUNCIL_PATHS": "   "}), "INFRA_COUNCIL_PATHS"
        )
        for value in (".", "/tmp", "../x", "docs/council/.."):
            with self.subTest(dir=value):
                self.assertBlocked(
                    r.run(APPLY, env={"INFRA_COUNCIL_DIR": value}), "INFRA_COUNCIL_DIR"
                )


class TestLintInterpreter(GuardCase):
    def no_yaml_python(self):
        venv = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, venv)
        subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True
        )
        return venv / "bin"

    def isolated_path(self, python_dir):
        """A PATH whose only python3 is the one in `python_dir`; every other tool kept."""
        bindir = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bindir)
        for d in os.environ["PATH"].split(":"):
            p = pathlib.Path(d)
            if not p.is_dir():
                continue
            for exe in p.iterdir():
                name = exe.name
                if name.startswith("python") or (bindir / name).exists():
                    continue
                if os.access(exe, os.X_OK):
                    (bindir / name).symlink_to(exe)
        (bindir / "python3").symlink_to(python_dir / "python3")
        return str(bindir)

    def test_a_python3_without_pyyaml_first_on_path_is_skipped(self):
        r = self.fresh(council({"lenses": ONE_FAMILY}))
        path = f"{self.no_yaml_python()}:{pathlib.Path(sys.executable).parent}:{os.environ['PATH']}"
        # still linted (C6), by the next python3 that has PyYAML
        self.assertBlocked(r.run(APPLY, path=path), "C6")

    def test_no_python3_with_pyyaml_blocks(self):
        r = self.fresh()
        path = self.isolated_path(self.no_yaml_python())
        self.assertBlocked(r.run(APPLY, path=path), "No python3 with PyYAML")

    def test_infra_council_python_overrides_path(self):
        r = self.fresh()
        path = self.isolated_path(self.no_yaml_python())
        env = {"INFRA_COUNCIL_PYTHON": sys.executable}
        self.assertAllowed(r.run(APPLY, path=path, env=env))

    def test_an_infra_council_python_without_pyyaml_blocks(self):
        r = self.fresh()
        env = {"INFRA_COUNCIL_PYTHON": str(self.no_yaml_python() / "python3")}
        self.assertBlocked(r.run(APPLY, env=env), "No python3 with PyYAML")


class TestFailsClosed(GuardCase):
    def test_a_missing_jq_blocks_with_exit_2(self):
        r = self.fresh()
        bindir = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bindir)
        for d in [str(pathlib.Path(sys.executable).parent)] + os.environ["PATH"].split(
            ":"
        ):
            p = pathlib.Path(d)
            if not p.is_dir():
                continue
            for exe in p.iterdir():
                name = exe.name
                if (
                    name != "jq"
                    and not (bindir / name).exists()
                    and os.access(exe, os.X_OK)
                ):
                    (bindir / name).symlink_to(exe)
        blocked, reason = r.run(APPLY, path=str(bindir))
        self.assertTrue(blocked)
        self.assertIn("EXIT2", reason)
        self.assertIn("jq not found on PATH", reason)

    def test_an_unexpected_command_failure_blocks_with_exit_2(self):
        # A git subcommand failing mid-hook must block, not fall through to an allow.
        r = self.fresh()
        bindir = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bindir)
        real_git = shutil.which("git")
        fake = bindir / "git"
        fake.write_text(
            "#!/bin/sh\n"
            'case " $* " in *" ls-tree "*) exit 3;; esac\n'
            f'exec "{real_git}" "$@"\n'
        )
        fake.chmod(0o755)
        path = f"{bindir}:{pathlib.Path(sys.executable).parent}:{os.environ['PATH']}"
        blocked, reason = r.run(APPLY, path=path)
        self.assertTrue(blocked)
        self.assertIn("EXIT2", reason)
        self.assertIn("internal error", reason)


if __name__ == "__main__":
    unittest.main()
