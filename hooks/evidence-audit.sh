#!/usr/bin/env bash
# evidence-audit.sh -- thin dispatcher around evidence-audit.py.
#
# Unified detection for the assertion classes the state-checks miss when stated
# without a probe: causal/external diagnoses (Lesson 2), absence claims
# (Lessons 12 + 15), and state-chain claims (Lesson 11). Replaces the former
# diagnosis-evidence-audit + claim-evidence-audit pair.
#
# Modes:
#   --stop          Stop hook: reads Stop JSON on stdin, scans the LAST turn,
#                   emits {"decision":"block","reason":...} on a hit (loop-guarded).
#   <transcript>    explicit file: prints flagged claims, exit 1 on a hit (CI/test).
#   (no args)       SessionStart digest of the newest transcripts; always exit 0.
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$DIR/evidence-audit.py"

MODE="${1:-}"

if [ "$MODE" = "--stop" ]; then
  python3 "$PY" --stop
  exit 0
fi

if [ -n "$MODE" ] && [ -f "$MODE" ]; then
  OUT="$(python3 "$PY" --file "$MODE")"; rc=$?
  if [ "$rc" -eq 1 ]; then
    echo "EVIDENCE-AUDIT: $(printf '%s\n' "$OUT" | grep -c .) untagged/unprobed claim(s) in $MODE:"
    printf '%s\n' "$OUT" | sed 's/^/  - turn /'
  else
    echo "EVIDENCE-AUDIT: clean ($MODE) -- causal/absence/state claims are probed or tagged."
  fi
  exit "$rc"
fi

PROJECTS="$HOME/.claude/projects"
if [ -d "$PROJECTS" ]; then
  FILES="$(find "$PROJECTS" -maxdepth 2 -name '*.jsonl' -type f -print0 2>/dev/null \
            | xargs -0 ls -t 2>/dev/null | head -2)"
  if [ -n "$FILES" ]; then
    # shellcheck disable=SC2086
    DIG="$(python3 "$PY" --digest $FILES 2>/dev/null)"
    if [ -n "$DIG" ]; then
      printf '[evidence-audit] Lessons 2/11/12/15 watch -- claims asserted without a probe or evidence tag:\n%s\n' "$DIG"
    fi
  fi
fi
exit 0
