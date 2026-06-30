#!/usr/bin/env bash
# PreToolUse(Bash) guard -- enforces claude-code-mastery LESSONS Lesson 14:
# never background a file-watching dev server.
#
# A backgrounded watcher (next dev / vite / nodemon / tsc --watch / *run dev) is
# not reaped after the turn ends -- the runtime stops tracking it and, rooted at
# the wrong directory, it grows without bound (one leaked past 65 GB RAM). The
# safe pattern is foreground start + curl + kill in ONE command, so the process
# dies with the turn. This blocks the backgrounded launch at the moment of the
# call instead of leaving the lesson as prose.
#
# Blocks when the command BOTH (a) launches a known file-watcher and (b) is
# backgrounded -- via the Bash tool's run_in_background flag OR a trailing `&`.
# A foreground watcher (start+curl+kill) is allowed. Receives tool JSON on stdin.
set -euo pipefail

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // ""')
[ "$TOOL" = "Bash" ] || exit 0

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
BG=$(echo "$INPUT" | jq -r '.tool_input.run_in_background // false')

# file-watcher launch signatures (dev servers / watch builds)
WATCH_RE='(^|[;&|[:space:]])(next[[:space:]]+dev|nuxt[[:space:]]+dev|astro[[:space:]]+dev|remix[[:space:]]+dev|gatsby[[:space:]]+develop|vite([[:space:]]|$)|vite[[:space:]]+dev|webpack[[:space:]]+serve|webpack-dev-server|ng[[:space:]]+serve|react-scripts[[:space:]]+start|nodemon|tsc[[:space:]].*(--watch|-w)([[:space:]]|$)|(npm|pnpm|yarn|bun)[[:space:]]+(run[[:space:]]+)?(dev|start|serve|watch))'

echo "$CMD" | grep -qE "$WATCH_RE" || exit 0
# allow non-watching builds that share a CLI name (vite build, next build, ...)
echo "$CMD" | grep -qE '(vite|next|nuxt|astro|remix|webpack)[[:space:]]+build' && exit 0

# backgrounded? run_in_background flag, OR a lone trailing `&` (not `&&`)
BGAMP=no
echo "$CMD" | grep -qE '(^|[^&])&[[:space:]]*$' && BGAMP=yes

if [ "$BG" = "true" ] || [ "$BGAMP" = "yes" ]; then
  REASON=$(printf 'Backgrounded dev server BLOCKED (LESSONS Lesson 14).\nCommand: %s\n\nA file-watching dev server run in the background is not reaped when the turn ends; rooted at the wrong dir it grows without bound (one leaked past 65 GB RAM).\n\nDo NOT background it. Start + probe + kill in ONE foreground command so it dies with the turn, e.g.\n  ( npm run dev >/tmp/dev.log 2>&1 & P=$!; sleep 4; curl -sf localhost:3000 >/tmp/out; kill "$P" )\nor let the test runner own the server lifecycle. Sweep `pgrep -fl vite` / `docker ps` at session end.' "$CMD")
  jq -cn --arg r "$REASON" '{continue:false, stopReason:$r}'
  exit 0
fi

exit 0
