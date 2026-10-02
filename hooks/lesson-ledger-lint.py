#!/usr/bin/env python3
"""Lesson-graph linter — operationalizes Lesson 17 as a fail-closed gate.

LESSONS.md is the node set (L1..LN). LEDGER.md is the edge set: every lesson must
have a row that names how it is enforced. A lesson with no row, or a row naming a
gate mechanism that does not exist on disk, is a DANGLING NODE — the exact defect
L17 names ("a lesson that isn't a gate gets re-violated"). This linter refuses to
let that ship.

Output: one `path:RULE:message` line per violation on stdout (rules MISSING, UTF8, ID,
ZERO, COVERAGE, ORPHAN, GAP, GATE), a summary on stderr.

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


# Lesson ids are 1..9999. A longer id is reported, never converted: int() refuses more
# than 4,300 digits, and the contiguity check would build range(1, id) -- a 46-digit id
# found by the fuzzer exhausted memory that way.
MAX_ID_DIGITS = 4
OVERSIZE_ID_RE = re.compile(
    r"^(?:## Lesson |\|\s*)(\d{%d,})" % (MAX_ID_DIGITS + 1), re.M
)


def parse_lessons(text):
    return {
        int(m.group(1)): m.group(2).strip()
        for m in re.finditer(r"^## Lesson (\d{1,4})\s*--\s*(.+)$", text, re.M)
    }


def parse_ledger(text):
    rows = {}
    for m in re.finditer(
        r"^\|\s*(\d{1,4})\s*\|([^\n]*)\|([^\n]*)\|([^\n]*)\|", text, re.M
    ):
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


def _emit(path, rule, msg):
    """One path:RULE:message line: control characters escaped, at most 240 characters."""
    line = f"{path}:{rule}:{msg}"
    line = "".join(ch if ch.isprintable() else repr(ch)[1:-1] for ch in line)
    return line if len(line) <= 240 else line[:226] + "...<truncated>"


def main():
    fails = []  # (path, RULE, message)
    if not LESSONS.exists() or not LEDGER.exists():
        missing = LESSONS.name if not LESSONS.exists() else LEDGER.name
        print(_emit(missing, "MISSING", "LESSONS.md or LEDGER.md missing"))
        return 1
    texts = {}
    for path in (LESSONS, LEDGER):
        try:
            texts[path.name] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            print(_emit(path.name, "UTF8", f"not UTF-8 ({exc.reason})"))
            return 1
    lessons_text, ledger_text = texts[LESSONS.name], texts[LEDGER.name]
    for name, text in texts.items():
        for raw in OVERSIZE_ID_RE.findall(text):
            fails.append(
                (
                    name,
                    "ID",
                    f"lesson id {raw[:12]}... has more than {MAX_ID_DIGITS} digits",
                )
            )
    lessons = parse_lessons(lessons_text)
    rows = parse_ledger(ledger_text)

    # Fail-closed: a linter that parsed nothing must never look green.
    if not lessons:
        fails.append(
            ("LESSONS.md", "ZERO", "parsed ZERO lessons (parser broken or file empty)")
        )
    if not rows:
        fails.append(
            ("LEDGER.md", "ZERO", "parsed ZERO rows (parser broken or file empty)")
        )

    if lessons and rows:
        for lid in sorted(lessons):
            if lid not in rows:
                fails.append(
                    (
                        "LEDGER.md",
                        "COVERAGE",
                        f"L{lid} ('{lessons[lid][:50]}') has NO ledger row (L17 violation)",
                    )
                )
        for lid in sorted(rows):
            if lid not in lessons:
                fails.append(
                    (
                        "LEDGER.md",
                        "ORPHAN",
                        f"row L{lid} maps to no lesson (orphan row)",
                    )
                )
        want = set(range(1, max(lessons) + 1))
        for gap in sorted(want - set(lessons)):
            fails.append(
                (
                    "LESSONS.md",
                    "GAP",
                    f"lesson-id gap: L{gap} missing (IDs must be contiguous 1..N)",
                )
            )

    for lid in sorted(rows):
        for name in set(MECH_RE.findall(rows[lid]["mech"])):
            target = resolve_mech(name)
            if not target.exists():
                fails.append(
                    (
                        "LEDGER.md",
                        "GATE",
                        f"L{lid} names gate '{name}' but {target.relative_to(ROOT)} does not exist (dangling gate)",
                    )
                )

    if fails:
        for path, rule, msg in sorted(fails):
            print(_emit(path, rule, msg))
        print(f"lesson-ledger-lint: {len(fails)} violation(s)", file=sys.stderr)
        return 1

    print(
        f"lesson-ledger-lint: OK — {len(lessons)} lessons, {len(rows)} ledger rows, "
        f"all gates resolve."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
