#!/usr/bin/env bash
# confidentiality-scrub.sh — generic confidentiality gate for public repos.
#
# Greps candidate text (staged diff, a commit range's files+messages, branch
# name, or arbitrary text files) against a denylist of extended-regex patterns
# that is NEVER committed to the repository it protects:
#   - locally:  $CONFIDENTIALITY_DENYLIST (default ~/.claude/scrub-denylist.txt)
#   - in CI:    the caller materializes a secret into a temp file and passes it
#               via CONFIDENTIALITY_DENYLIST (values are masked in CI logs).
#
# Fail-closed is opt-in so that public adopters without a denylist are not
# broken: if the list is absent, the gate SKIPS with a warning unless
# CONFIDENTIALITY_SCRUB_REQUIRE=1, in which case a missing list is a failure.
#
# Usage:
#   confidentiality-scrub.sh --staged                 # staged diff + branch name
#   confidentiality-scrub.sh --range <A>..<B>         # files changed + commit messages in range
#   confidentiality-scrub.sh --text <file> [file...]  # arbitrary text (PR title/body dump)
#
# Exit: 0 clean or skipped; 1 match found or list required-but-missing; 2 usage.

set -euo pipefail

DENYLIST="${CONFIDENTIALITY_DENYLIST:-$HOME/.claude/scrub-denylist.txt}"

if [[ ! -s "$DENYLIST" ]]; then
  if [[ "${CONFIDENTIALITY_SCRUB_REQUIRE:-0}" == "1" ]]; then
    echo "confidentiality-scrub: FAIL — denylist required but missing/empty at $DENYLIST" >&2
    exit 1
  fi
  echo "confidentiality-scrub: SKIP — no denylist at $DENYLIST (set CONFIDENTIALITY_SCRUB_REQUIRE=1 to fail closed)" >&2
  exit 0
fi

fail=0

scan_stream() {
  # $1 = label; stdin = text to scan. Reports line numbers, not matched text,
  # so a CI log never carries the protected term even unmasked.
  local label="$1"
  local hits
  hits=$(grep -n -E -f "$DENYLIST" - 2>/dev/null | cut -d: -f1 | paste -sd, - || true)
  if [[ -n "$hits" ]]; then
    echo "confidentiality-scrub: MATCH in ${label} (line(s): ${hits})" >&2
    fail=1
  fi
}

case "${1:-}" in
  --staged)
    # scan_stream must not run in a pipeline stage (subshell would drop fail=1)
    scan_stream "staged diff" < <(git diff --cached --unified=0 | grep '^+' || true)
    scan_stream "branch name" < <(git rev-parse --abbrev-ref HEAD)
    ;;
  --range)
    [[ -n "${2:-}" ]] || { echo "usage: $0 --range A..B" >&2; exit 2; }
    range="$2"
    while IFS= read -r f; do
      if [[ -f "$f" ]]; then scan_stream "file ${f}" < "$f"; fi
    done < <(git diff --name-only "$range" -- 2>/dev/null)
    scan_stream "commit messages ${range}" < <(git log --format='%s%n%b' "$range")
    scan_stream "branch name" < <(git rev-parse --abbrev-ref HEAD)
    ;;
  --text)
    shift
    [[ $# -ge 1 ]] || { echo "usage: $0 --text <file>..." >&2; exit 2; }
    for f in "$@"; do
      scan_stream "text ${f}" < "$f"
    done
    ;;
  *)
    echo "usage: $0 --staged | --range A..B | --text <file>..." >&2
    exit 2
    ;;
esac

if [[ "$fail" == "1" ]]; then
  echo "confidentiality-scrub: FAIL — protected terms present. Remove them before commit/push." >&2
  exit 1
fi
echo "confidentiality-scrub: clean"
