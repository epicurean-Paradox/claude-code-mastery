#!/usr/bin/env bash
# SessionStart detection hook -- closes the DETECTION end of the lesson loop so a
# re-violation surfaces without the operator having to notice it.
# Prints a short digest to stdout (becomes session context). Always exits 0.
set -uo pipefail

LEDGER="$HOME/claude-code-mastery/LEDGER.md"
FRONTEND="$HOME/npm-dashboard/frontend/src"
SCAFFOLD_RE='PAGE[[:space:]]+[0-9]+[[:space:]]+OF[[:space:]]+[0-9]+|(←[[:space:]]*→|to navigate)|StageLabel|(HAPPY|NON-?HAPPY|WARN|ERROR)[[:space:]]*(・|·|\|)[[:space:]]*[0-9N]'

OUT=""

# 1. Open defects: SOFT (ungated) lessons in the ledger.
if [ -f "$LEDGER" ]; then
  SOFT=$(grep -cE '\| SOFT \|' "$LEDGER" 2>/dev/null || echo 0)
  [ "$SOFT" -gt 0 ] && OUT="${OUT}lesson-ledger: ${SOFT} lessons still SOFT (ungated = open defects). See ~/claude-code-mastery/LEDGER.md."$'\n'
fi

# 2. Detection: prototype scaffold ALREADY in first-party frontend source
#    (catches violations that predate the write-time guard, e.g. the live stepper).
if [ -d "$FRONTEND" ]; then
  HITS=$(grep -rlInE "$SCAFFOLD_RE" "$FRONTEND" 2>/dev/null \
    | grep -vE '\.(test|spec|stories)\.[jt]sx?$|/__mocks__/|/e2e/' \
    | head -10 || true)
  if [ -n "$HITS" ]; then
    N=$(echo "$HITS" | grep -c . )
    OUT="${OUT}LESSON 3 VIOLATION IN TREE: prototype scaffold in ${N} frontend source file(s) (dev assets shipped as product):"$'\n'
    OUT="${OUT}$(echo "$HITS" | sed 's|^|  - |')"$'\n'
  fi
fi

if [ -n "$OUT" ]; then
  printf '[lesson-loop-audit]\n%s' "$OUT"
fi
exit 0
