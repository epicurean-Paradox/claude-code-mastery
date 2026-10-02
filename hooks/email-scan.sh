#!/usr/bin/env bash
# email-scan.sh -- fails when a tracked file in a git repository contains an email
# address, other than the reserved example domains of RFC 2606 / RFC 6761
# (example.com/.net/.org, .example, .invalid, .test, .localhost).
#
# A public methodology repo carries no person's address; a fixture that needs one uses
# a reserved domain. Prints file:line for each hit -- never the address itself, so the
# CI log does not republish what it caught.
#
# Catches accidental commits, not deliberate obfuscation (`jane @ acme`, %40, entities).
#
# Usage: email-scan.sh [REPO]     Exit: 0 clean, 1 hits, 2 not a repo / nothing tracked /
#                                  git grep failed.

set -euo pipefail

REPO="${1:-.}"
git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1 || {
    echo "email-scan: $REPO is not a git repository" >&2
    exit 2
}

# Any character but whitespace and delimiters, so IDN and non-ASCII addresses match too.
# Bracket-expression body: ']' and '[' first, then whitespace and delimiters. Anything
# else (non-ASCII included) may be part of an address.
NOT="][[:space:]<>\"()'\`,;:@"
EMAIL="[^${NOT}]+@[^${NOT}]+[.][^${NOT}.]{2,}"
RESERVED='@([A-Za-z0-9-]+[.])*(example[.](com|net|org)|example|invalid|test|localhost)$'

[ -n "$(git -C "$REPO" ls-files)" ] || {
    echo "email-scan: no tracked files in $REPO -- nothing scanned is not a pass" >&2
    exit 2
}

# One line per address (-o): file:line:address. -a: binary files (document metadata)
# are scanned too. git grep exits 1 for "no match"; anything above is a failure.
RC=0
RAW=$(LC_ALL=C git -C "$REPO" grep -anoE "$EMAIL" -- . 2>/dev/null) || RC=$?
if [ "$RC" -gt 1 ]; then
    echo "email-scan: git grep failed (exit $RC) in $REPO" >&2
    exit 2
fi
HITS=$(printf '%s\n' "$RAW" | grep -viE "$RESERVED" | grep . || true)
if [ -z "$HITS" ]; then
    echo "email-scan: clean ($(git -C "$REPO" ls-files | wc -l | tr -d ' ') tracked files)"
    exit 0
fi
echo "email-scan: $(printf '%s\n' "$HITS" | grep -c .) address(es) outside reserved example domains:"
printf '%s\n' "$HITS" | cut -d: -f1,2 | sort -u | sed 's/^/  /'
exit 1
