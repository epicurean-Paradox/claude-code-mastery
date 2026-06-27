#!/usr/bin/env bash
# PreToolUse guard for Claude Code -- enforces claude-code-mastery LESSONS Lesson 3
# (distinguish dev assets from desired outcome) at the moment of violation.
#
# Blocks a Write/Edit/MultiEdit that injects design-PROTOTYPE SCAFFOLD into
# first-party frontend SOURCE. The scaffold is a development asset (review
# affordances, state-gallery navigation, designer captions) and must NOT ship.
# This closes the loop the lesson described: the lesson was prose and got
# re-violated (the "PAGE 0 OF 3" stepper reached production). Now it fails loud.
#
# Receives the tool-call JSON on stdin. Prints {"continue":false,...} to block.
set -euo pipefail

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // ""')
case "$TOOL" in
  Write|Edit|MultiEdit) ;;
  *) exit 0 ;;
esac

FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')

# Guard FIRST-PARTY frontend source only. Skip the prototype/design corpus,
# tests, stories, and any .html mockups -- scaffold is legitimate THERE.
echo "$FILE" | grep -qE '/frontend/src/' || exit 0
echo "$FILE" | grep -qE 'product-design|/patterns/|\.html$|\.(test|spec|stories)\.[jt]sx?$|/e2e/|/__mocks__/|/fixtures?/' && exit 0

# The new content being written (Write=content, Edit=new_string, MultiEdit=all edits).
CONTENT=$(echo "$INPUT" | jq -r '
  (.tool_input.content // "")
  + "\n" + (.tool_input.new_string // "")
  + "\n" + ([.tool_input.edits[]?.new_string] | join("\n"))
')

# Unambiguous prototype-scaffold signatures (low false-positive):
#  - the multi-step state-gallery stepper ("PAGE 0 OF 3")
#  - the reviewer keyboard-navigation hint
#  - the StageLabel component / its "HAPPY 01" banners
#  - designer state codes addressed to the prototype's reader
SCAFFOLD_RE='PAGE[[:space:]]+[0-9]+[[:space:]]+OF[[:space:]]+[0-9]+|(←[[:space:]]*→|to navigate)|StageLabel|(HAPPY|NON-?HAPPY|WARN|ERROR)[[:space:]]*(・|·|\|)[[:space:]]*[0-9N]'
HITS=$(echo "$CONTENT" | grep -inE "$SCAFFOLD_RE" 2>/dev/null | head -5 || true)

if [ -n "$HITS" ]; then
  REASON=$(printf 'Prototype scaffold blocked in frontend source (LESSONS Lesson 3: dev assets != product).\nFile: %s\nMatched dev-reference markers:\n%s\n\nThis scaffold (state-gallery stepper / reviewer nav hint / StageLabel banners) is a DEVELOPMENT asset and must not ship. Render from real state instead.\nIf this is genuinely product copy (not scaffold), rephrase, or write to the prototype corpus (docs/product-design), or disable this guard for the edit.' "$FILE" "$HITS")
  jq -cn --arg r "$REASON" '{continue:false, stopReason:$r}'
  exit 0
fi

exit 0
