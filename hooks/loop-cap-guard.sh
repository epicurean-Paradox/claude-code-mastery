#!/usr/bin/env bash
# PreToolUse hook (matcher: CronCreate|ScheduleWakeup) -- blocks scheduling an
# unattended loop iteration whose input declares no stop primitive.
#
# Lesson 22: an unattended loop needs a hard iteration cap, a budget cap, and
# an explicit escalation path, declared in the launch config/message -- or it
# ends by accident (runs forever, or declares false victory). This hook is the
# HARD end: a CronCreate / ScheduleWakeup call whose input carries none of the
# recognized stop-primitive markers is blocked at call time.
#
# Recognized markers (case-insensitive, anywhere in the tool input): iteration
# caps (max iterations/turns/runs, "stop after N", "N more iterations"), budget
# caps ("budget", token/spend caps), expiry ("expires", "until <date>", end
# conditions), or an escalation path ("escalate", "page the operator", "notify
# and stop"). Declaring even one names the loop's exit; the block message asks
# for all three.
#
# Register in ~/.claude/settings.json under PreToolUse with matcher
# "CronCreate|ScheduleWakeup".

set -euo pipefail

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""')

# Only gate the scheduling tools
case "$TOOL" in
    CronCreate|ScheduleWakeup) ;;
    *) exit 0 ;;
esac

ARGS=$(printf '%s' "$INPUT" | jq -c '.tool_input // {}')

# Stop-primitive markers. POSIX classes only (GNU/BSD grep parity).
PATTERN='max[_ -]?(iter|turn|run|loop)|iteration[[:space:]]+cap|stop[[:space:]]+after|more[[:space:]]+iterations?|budget|token[[:space:]]+cap|spend[[:space:]]+cap|expir|until[[:space:]]|end[[:space:]]+condition|escalat|page[[:space:]]+the[[:space:]]+operator|notify[[:space:]]+and[[:space:]]+stop|final[[:space:]]+(run|iteration)|one[- ]shot|run[- ]once'

if printf '%s\n' "$ARGS" | grep -qiE "$PATTERN"; then
    exit 0
fi

REASON=$(printf 'Unattended-loop launch BLOCKED (LESSONS Lesson 22).\nTool: %s\n\nThe launch input declares no stop primitive. Every unattended loop states, in its launch config/message, all three of:\n  1. a hard iteration cap (e.g. "stop after 10 iterations")\n  2. a hard budget cap (e.g. "budget: 500k tokens")\n  3. an escalation path (e.g. "on cap or stall, notify the operator and stop")\n\nRe-issue the call with the stop primitives stated in the prompt/config. Continuation is the default; termination must be engineered.' "$TOOL")
jq -cn --arg r "$REASON" '{continue:false, stopReason:$r}'
exit 0
