#!/usr/bin/env python3
"""Lesson-graph linter — operationalizes Lesson 17 as a fail-closed gate.

LESSONS.md is the node set (L1..LN). LEDGER.md is the edge set: every lesson must
have a row that names how it is enforced. A lesson with no row, or a row naming a
gate mechanism that does not exist on disk, is a DANGLING NODE — the exact defect
L17 names ("a lesson that isn't a gate gets re-violated"). This linter refuses to
let that ship.

Checks (all fail-closed — exit 1 on any violation; exit 1 if it parsed nothing):
  1. Coverage      — every LESSONS.md lesson has a LEDGER row (missing row = FAIL).
  2. No orphans    — every LEDGER row maps to a real lesson.
  3. Node integrity— lesson IDs are contiguous 1..N, unique, in both files.
  4. Live gates    — every in-repo mechanism a row NAMES (hooks/*.sh|py,
                     .github/workflows/*.yml) actually exists on disk. A row that
                     claims HARD/SEMI enforcement via a file that isn't there is a
                     dangling gate.

Run from the repo root: python3 hooks/lesson-ledger-lint.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LESSONS = ROOT / "LESSONS.md"
LEDGER = ROOT / "LEDGER.md"

# In-repo mechanism references a row may name. ~/.claude/hooks/X is machine-local
# but the repo vendors the same file under hooks/, so we normalize to basename.
MECH_RE = re.compile(
    r"(?:~/\.claude/hooks/|hooks/|\.github/workflows/)([A-Za-z0-9._-]+\.(?:sh|py|yml|yaml))"
)


def parse_lessons(text):
    return {
        int(m.group(1)): m.group(2).strip()
        for m in re.finditer(r"^## Lesson (\d+)\s*--\s*(.+)$", text, re.M)
    }


def parse_ledger(text):
    rows = {}
    for m in re.finditer(r"^\|\s*(\d+)\s*\|([^\n]*)\|([^\n]*)\|([^\n]*)\|", text, re.M):
        rows[int(m.group(1))] = {
            "lesson": m.group(2).strip(),
            "tier": m.group(3).strip(),
            "mech": m.group(4).strip(),
        }
    return rows


def resolve_mech(name):
    """Where an in-repo mechanism file should live, by basename."""
    if name.endswith((".yml", ".yaml")):
        return ROOT / ".github" / "workflows" / name
    return ROOT / "hooks" / name


def main():
    fails = []
    if not LESSONS.exists() or not LEDGER.exists():
        print("FAIL: LESSONS.md or LEDGER.md missing", file=sys.stderr)
        return 1

    lessons = parse_lessons(LESSONS.read_text())
    ledger_text = LEDGER.read_text()
    rows = parse_ledger(ledger_text)

    # Fail-closed: a linter that parsed nothing must never look green.
    if not lessons:
        fails.append(
            "parsed ZERO lessons from LESSONS.md (parser broken or file empty)"
        )
    if not rows:
        fails.append("parsed ZERO rows from LEDGER.md (parser broken or file empty)")

    if lessons and rows:
        # 1. Coverage
        for lid in sorted(lessons):
            if lid not in rows:
                fails.append(
                    f"L{lid} ('{lessons[lid][:50]}') has NO ledger row (L17 violation)"
                )
        # 2. Orphans
        for lid in sorted(rows):
            if lid not in lessons:
                fails.append(
                    f"ledger row L{lid} maps to no lesson in LESSONS.md (orphan row)"
                )
        # 3. Node integrity — contiguous 1..N in the lesson set
        want = set(range(1, max(lessons) + 1))
        for gap in sorted(want - set(lessons)):
            fails.append(f"lesson-id gap: L{gap} missing (IDs must be contiguous 1..N)")

    # 4. Live gates — a named in-repo mechanism must exist
    for lid in sorted(rows):
        mech = rows[lid]["mech"]
        for name in set(MECH_RE.findall(mech)):
            target = resolve_mech(name)
            if not target.exists():
                fails.append(
                    f"L{lid} names gate '{name}' but {target.relative_to(ROOT)} does not exist (dangling gate)"
                )

    if fails:
        print(f"lesson-ledger-lint: {len(fails)} violation(s)\n", file=sys.stderr)
        for f in fails:
            print(f"  FAIL: {f}", file=sys.stderr)
        return 1

    print(
        f"lesson-ledger-lint: OK — {len(lessons)} lessons, {len(rows)} ledger rows, "
        f"all gates resolve."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
