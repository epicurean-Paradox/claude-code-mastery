#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash) -- blocks `git commit` when the staged diff
# contains credential patterns (AWS access keys, PEM private keys, assigned
# secrets/passwords/tokens). Receives Claude Code tool JSON on stdin.
#
# This is the write-time end of Lesson 13 (a migrated secret is still a leaked
# secret): stop the credential from entering history at all. gitleaks in CI is
# the push-time end; issuer-side rotation remains the only true close once a
# secret has leaked.
#
# Register in ~/.claude/settings.json under PreToolUse with matcher "Bash".

set -euo pipefail

INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""')

# Only intercept git commit commands. Single-dash options with a separate
# argument (-C <path>, -c <key=val>) are matched explicitly; exotic forms
# (--git-dir=...) fall through to gitleaks in CI, the push-time end.
printf '%s\n' "$CMD" | grep -qE 'git[[:space:]]+((-[cC][[:space:]]+[^[:space:]]+|-[^-][^[:space:]]*)[[:space:]]+)*commit' || exit 0

# Extract repo path from a -C flag if present, otherwise use cwd
REPO=$(printf '%s\n' "$CMD" | sed -n 's/.*git -C \([^ ]*\).*/\1/p' | head -1)
if [ -n "$REPO" ]; then
    DIFF=$(git -C "$REPO" diff --staged 2>/dev/null || true)
else
    DIFF=$(git diff --staged 2>/dev/null || true)
fi

[ -z "$DIFF" ] && exit 0

# Scan added lines (+) only -- skip diff headers (+++)
ADDED=$(printf '%s\n' "$DIFF" | grep -E '^\+[^+]' || true)
[ -z "$ADDED" ] && exit 0

# Patterns: AWS access keys, GitHub tokens, Slack tokens, PEM private keys,
# assigned secrets/passwords/tokens.
# POSIX classes only -- must behave identically under GNU and BSD grep.
SQ="'"
PATTERN="AKIA[0-9A-Z]{16}"
PATTERN="$PATTERN|gh[pousr]_[A-Za-z0-9]{36}"
PATTERN="$PATTERN|github_pat_[A-Za-z0-9_]{22,}"
PATTERN="$PATTERN|xox[baprs]-[A-Za-z0-9-]{10,}"
PATTERN="$PATTERN|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY"
PATTERN="$PATTERN|(api[_-]?key|api[_-]?secret|auth[_-]?token|access[_-]?token|oauth[_-]?token|secret[_-]?key|private[_-]?key|password|passwd)[[:space:]]*[:=][[:space:]]*[\"${SQ}\`][^\"${SQ}\`]{6,}"
FOUND=$(printf '%s\n' "$ADDED" | grep -iE "$PATTERN" || true)

if [ -n "$FOUND" ]; then
    REASON=$(printf 'Secret/credential pattern detected in staged diff (LESSONS Lesson 13).\nRun: git diff --staged\nReview the flagged lines before committing. If a value already left the machine, vaulting or history-scrubbing does not close the exposure -- only issuer-side rotation + revocation does.')
    jq -cn --arg r "$REASON" '{continue:false, stopReason:$r}'
    exit 0
fi

exit 0
