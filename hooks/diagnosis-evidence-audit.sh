#!/usr/bin/env bash
# diagnosis-evidence-audit.sh -- thin dispatcher around diagnosis-evidence-audit.py
#
# Closes the DETECTION end of Lesson 2 generalised to ANY causal claim about a
# discrepancy (a bug, a failed step, or two numbers that disagree). Flags a
# causal / external-suspect diagnosis ("snapshot", "deploy", "stale", "race",
# "242 vs local", "not a bug") asserted with no source-of-truth probe and no
# [verified:]/[hypothesis:] tag. Real case: "the £527K is the 242 snapshot".
#
# Modes:
#   --stop          Stop hook: reads the Stop-event JSON on stdin, scans only the
#                   LAST assistant turn, emits {"decision":"block","reason":...}
#                   when an untagged causal diagnosis is found (loop-guarded).
#                   Tightest loop -- catches the claim same-session, before it ships.
#   <transcript>    explicit file: prints flagged assertions, exit 1 on a hit
#                   (self-test / CI / usable standalone).
#   (no args)       SessionStart digest: scans the newest project transcripts,
#                   prints a short digest to stdout, always exit 0.
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$DIR/diagnosis-evidence-audit.py"

MODE="${1:-}"

# ---- Stop hook ----
if [ "$MODE" = "--stop" ]; then
  python3 "$PY" --stop
  exit 0
fi

# ---- explicit file (self-test / CI / Stop-on-one-file) ----
if [ -n "$MODE" ] && [ -f "$MODE" ]; then
  OUT="$(python3 "$PY" --file "$MODE")"; rc=$?
  if [ "$rc" -eq 1 ]; then
    echo "DIAGNOSIS-EVIDENCE-AUDIT: $(printf '%s\n' "$OUT" | grep -c .) untagged causal/external diagnosis assertion(s) in $MODE:"
    printf '%s\n' "$OUT" | sed 's/^/  - turn /'
  else
    echo "DIAGNOSIS-EVIDENCE-AUDIT: clean ($MODE) -- every causal/external diagnosis is tagged or probed."
  fi
  exit "$rc"
fi

# ---- SessionStart digest (newest 2 transcripts, never block) ----
PROJECTS="$HOME/.claude/projects"
if [ -d "$PROJECTS" ]; then
  FILES="$(find "$PROJECTS" -maxdepth 2 -name '*.jsonl' -type f -print0 2>/dev/null \
            | xargs -0 ls -t 2>/dev/null | head -2)"
  if [ -n "$FILES" ]; then
    # shellcheck disable=SC2086
    DIG="$(python3 "$PY" --digest $FILES 2>/dev/null)"
    if [ -n "$DIG" ]; then
      printf '[diagnosis-evidence-audit] Lesson 2 watch -- causal claims asserted without a source-of-truth probe or [hypothesis:] tag:\n%s\n' "$DIG"
    fi
  fi
fi
exit 0
