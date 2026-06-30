#!/usr/bin/env bash
# PreCompact hook -- archive the FULL transcript before the SDK compacts it.
#
# Compaction is the moment of maximum information loss: it replaces older turns
# with a summary mid-session. The detection hooks (evidence-audit, lesson-loop-
# audit) read the raw transcript under ~/.claude/projects/*.jsonl -- exactly the
# history compaction summarizes away. Without this archive, the audit backstop
# goes blind at the moment of greatest loss. So snapshot the transcript first;
# the audits (and a human) can still read pre-compaction history afterwards.
#
# Receives the PreCompact event JSON on stdin: { transcript_path, trigger
# (manual|auto), session_id, ... }. Best-effort, never blocks compaction.
set -uo pipefail

INPUT="$(cat)"
TP="$(printf '%s' "$INPUT" | jq -r '.transcript_path // ""')"
TRIGGER="$(printf '%s' "$INPUT" | jq -r '.trigger // "auto"')"

[ -n "$TP" ] && [ -f "$TP" ] || exit 0

ARCHIVE_DIR="$HOME/.claude/precompact-archives"
mkdir -p "$ARCHIVE_DIR" || exit 0

TS="$(date +%Y%m%dT%H%M%S)"
BASE="$(basename "$TP" .jsonl)"
DEST="$ARCHIVE_DIR/${BASE}.${TRIGGER}.${TS}.jsonl"

if cp "$TP" "$DEST" 2>/dev/null; then
  # stderr (not stdout) so we never interfere with the hook's output protocol
  echo "[precompact-archive] transcript snapshot -> $DEST (trigger=$TRIGGER)" >&2
fi
exit 0
