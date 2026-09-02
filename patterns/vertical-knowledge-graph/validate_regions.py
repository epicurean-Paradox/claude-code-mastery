#!/usr/bin/env python3
"""Fail-closed validator for a vertical-knowledge-graph regions.yaml.

Rules enforced (see regions.schema.md):
  E1  pattern key must be vertical-knowledge-graph@1
  E2  every region's vertical must be in the declared vocabulary; one region per vertical
  E3  status: observed requires a complete evidence block
      (source-health, row-counts, last-run, verified-at, describes-commit)
  E4  observed evidence older than the freshness window demotes the region (error)
  E5  rbac.enforced: true requires rbac.enforcement_point
  E6  row-counts must all be > 0 for an observed region
  E7  empty sources/destinations allowed only when declared-only
  E8  conversation-intelligence or hr sources require erasure_lineage.subject_key
  E9  a parse that yields zero regions is an error (fail-closed)
  E10 consumers empty on an observed region is an error (warning when declared-only)
  W1  verticals with no region entry are reported DARK (warning)

Exit codes: 0 pass, 1 any error, 2 unreadable input.
"""

import sys
from datetime import date, datetime, timezone

try:
    import yaml
except ImportError:  # pragma: no cover
    print("validate_regions: PyYAML required (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

PATTERN_ID = "vertical-knowledge-graph@1"
SOURCE_CATEGORIES = {
    "crm",
    "marketing",
    "ticketing",
    "vcs",
    "chat",
    "hr",
    "conversation-intelligence",
    "product-analytics",
    "billing",
    "winloss",
    "docs",
    "other",
}
EVIDENCE_KEYS = {
    "source-health",
    "row-counts",
    "last-run",
    "verified-at",
    "describes-commit",
}
LINEAGE_CATEGORIES = {"conversation-intelligence", "hr"}


def _parse_date(value):
    if isinstance(value, (date, datetime)):
        return (
            value
            if isinstance(value, date) and not isinstance(value, datetime)
            else value.date()
        )
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def validate(doc, today=None):
    """Return (errors, warnings) lists of strings."""
    today = today or datetime.now(timezone.utc).date()
    errors, warnings = [], []

    if not isinstance(doc, dict):
        return (["E9: document is not a mapping"], [])
    if doc.get("pattern") != PATTERN_ID:
        errors.append(f"E1: pattern must be '{PATTERN_ID}', got {doc.get('pattern')!r}")

    vocabulary = doc.get("verticals") or []
    if not vocabulary:
        errors.append("E2: top-level verticals vocabulary is required")

    default_window = int(doc.get("stale-after-days", 14))
    regions = doc.get("regions")
    if not regions:
        errors.append("E9: zero regions parsed (fail-closed)")
        return (errors, warnings)

    seen = set()
    for i, region in enumerate(regions):
        tag = f"region[{i}]"
        if not isinstance(region, dict):
            errors.append(f"E9: {tag} is not a mapping")
            continue
        vertical = region.get("vertical")
        tag = f"region[{vertical or i}]"
        if vertical not in vocabulary:
            errors.append(f"E2: {tag} vertical {vertical!r} not in vocabulary")
        if vertical in seen:
            errors.append(f"E2: duplicate region for vertical {vertical!r}")
        seen.add(vertical)

        status = region.get("status")
        if status not in ("observed", "declared-only"):
            errors.append(
                f"E3: {tag} status must be observed|declared-only, got {status!r}"
            )
            status = "declared-only"

        tier = region.get("sensitivity_tier")
        if not isinstance(tier, int) or not 1 <= tier <= 4:
            errors.append(f"E3: {tag} sensitivity_tier must be int 1..4")

        sources = region.get("sources") or []
        destinations = region.get("destinations") or []
        if status == "observed" and (not sources or not destinations):
            errors.append(
                f"E7: {tag} observed region requires non-empty sources and destinations"
            )
        categories = set()
        for src in sources:
            cat = (src or {}).get("category")
            if cat not in SOURCE_CATEGORIES:
                errors.append(f"E7: {tag} source category {cat!r} unknown")
            categories.add(cat)

        if categories & LINEAGE_CATEGORIES:
            lineage = region.get("erasure_lineage") or {}
            if not lineage.get("subject_key"):
                errors.append(
                    f"E8: {tag} has {sorted(categories & LINEAGE_CATEGORIES)} sources "
                    "but no erasure_lineage.subject_key"
                )

        rbac = region.get("rbac") or {}
        if not rbac.get("scope"):
            errors.append(f"E5: {tag} rbac.scope required")
        if rbac.get("enforced") is True and not rbac.get("enforcement_point"):
            errors.append(f"E5: {tag} rbac.enforced true without enforcement_point")
        if "enforced" not in rbac:
            errors.append(f"E5: {tag} rbac.enforced (true|false) required")

        consumers = region.get("consumers") or []
        if not consumers:
            msg = f"{tag} has no named consumer (DEFERRED per adoption gate)"
            (errors if status == "observed" else warnings).append(
                ("E10: " if status == "observed" else "W: ") + msg
            )

        if status == "observed":
            evidence = region.get("evidence") or {}
            missing = EVIDENCE_KEYS - set(evidence)
            if missing:
                errors.append(
                    f"E3: {tag} observed without evidence keys {sorted(missing)}"
                )
            else:
                window = int(region.get("stale-after-days", default_window))
                try:
                    verified = _parse_date(evidence["verified-at"])
                    if (today - verified).days > window:
                        errors.append(
                            f"E4: {tag} evidence verified-at {verified} exceeds "
                            f"{window}-day window (demoted)"
                        )
                except (ValueError, TypeError):
                    errors.append(f"E4: {tag} evidence verified-at unparseable")
                counts = evidence.get("row-counts") or {}
                bad = [
                    k for k, v in counts.items() if not (isinstance(v, int) and v > 0)
                ]
                if not counts or bad:
                    errors.append(
                        f"E6: {tag} row-counts must be non-empty and all > 0 "
                        f"(bad: {bad or 'empty'})"
                    )

    dark = [v for v in vocabulary if v not in seen]
    for v in dark:
        warnings.append(f"W1: vertical {v!r} is DARK (no region entry)")
    return (errors, warnings)


def main(argv):
    if len(argv) != 2:
        print("usage: validate_regions.py <regions.yaml>", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        print(f"validate_regions: cannot read/parse {argv[1]}: {exc}", file=sys.stderr)
        return 2
    errors, warnings = validate(doc)
    for line in warnings:
        print(f"WARN  {line}")
    for line in errors:
        print(f"ERROR {line}")
    print(f"validate_regions: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
