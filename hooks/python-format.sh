#!/usr/bin/env bash
# PostToolUse hook (matcher: Write|Edit) -- auto-formats Python files with ruff
# after Claude writes or edits them. Receives Claude Code tool JSON on stdin.
#
# Hygiene, not a gate: silently no-ops when the file is not Python, no longer
# exists, or ruff is not installed. Never fails the tool call.
#
# Register in ~/.claude/settings.json under PostToolUse with matcher "Write|Edit".

set -euo pipefail

INPUT=$(cat)
FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // ""')

# Only process Python files
printf '%s\n' "$FILE" | grep -qE '\.py$' || exit 0

# Skip if file doesn't exist (e.g., delete operations)
[ -f "$FILE" ] || exit 0

# Resolve ruff: PATH first, then common install locations
RUFF=$(command -v ruff || true)
if [ -z "$RUFF" ]; then
    for CANDIDATE in /opt/homebrew/bin/ruff /usr/local/bin/ruff "$HOME/.local/bin/ruff"; do
        if [ -x "$CANDIDATE" ]; then
            RUFF=$CANDIDATE
            break
        fi
    done
fi
[ -n "$RUFF" ] || exit 0

"$RUFF" format --quiet "$FILE" 2>/dev/null || true

exit 0
