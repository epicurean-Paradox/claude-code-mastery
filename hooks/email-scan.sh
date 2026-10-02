#!/usr/bin/env bash
# email-scan.sh -- fails when a tracked file in a git repository contains an email
# address, other than the reserved example domains of RFC 2606 / RFC 6761
# (example.com/.net/.org, .example, .invalid, .test, .localhost).
#
# A public methodology repo carries no person's address; a fixture that needs one uses
# a reserved domain. Prints file:line for each hit -- never the address itself, so the
# CI log does not republish what it caught.
#
# Usage: email-scan.sh [REPO]     Exit: 0 clean, 1 hits, 2 not a git repository.

set -euo pipefail

REPO="${1:-.}"
git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1 || {
    echo "email-scan: $REPO is not a git repository" >&2
    exit 2
}

EMAIL='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+[.][A-Za-z]{2,}'
RESERVED='@([A-Za-z0-9-]+[.])*(example[.](com|net|org)|example|invalid|test|localhost)$'

# One line per address (-o): file:line:address. Keep those outside the reserved domains.
HITS=$(git -C "$REPO" grep -nIoE "$EMAIL" -- . 2>/dev/null | grep -vE "$RESERVED" || true)
if [ -z "$HITS" ]; then
    echo "email-scan: clean ($(git -C "$REPO" ls-files | wc -l | tr -d ' ') tracked files)"
    exit 0
fi
echo "email-scan: $(printf '%s\n' "$HITS" | grep -c .) address(es) outside reserved example domains:"
printf '%s\n' "$HITS" | cut -d: -f1,2 | sort -u | sed 's/^/  /'
exit 1
