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
  E9  a parse that yields zero regions is an error (fail-closed); so is a field whose
      value has the wrong type (reported, never a crash)
  E10 consumers empty on an observed region is an error (warning when declared-only)
  W1  verticals with no region entry are reported DARK (warning)

Exit codes: 0 pass, 1 any error, 2 unreadable input (including a file over MAX_BYTES,
invalid UTF-8, or any YAML alias). Every output line is one physical line of at most
MAX_LINE characters, so a document value can neither flood nor forge the report.
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
MAX_BYTES = 1_048_576  # a hand-written regions.yaml is a few KB; bounds parse work
MAX_LINE = 240
TRUNCATED = "...<truncated>"
# Declared type per field. None is "absent" for list/dict fields (the checks below use
# `or []` / `or {}`), and a wrong type is an E9 error instead of a TypeError downstream.
DOC_SHAPES = {"verticals": list, "stale-after-days": int, "regions": list}
REGION_SHAPES = {
    "vertical": str,
    "sources": list,
    "destinations": list,
    "entities": list,
    "consumers": list,
    "rbac": dict,
    "evidence": dict,
    "erasure_lineage": dict,
    "stale-after-days": int,
}


class _NoAliasLoader(yaml.SafeLoader):
    """SafeLoader that refuses aliases (*name).

    A hand-written regions.yaml has no use for them, and they are the cheapest way to
    exhaust the validator: a 427-byte file of nested aliases expanded to 5.8 GB of memory
    and 2 GB of output through the E1 message's repr().
    """

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise yaml.YAMLError("YAML aliases (*name) are not allowed")
        return super().compose_node(parent, index)


def _shape_errors(tag, mapping, shapes):
    out = []
    for key, typ in shapes.items():
        if key not in mapping or (mapping[key] is None and typ in (list, dict)):
            continue
        value = mapping[key]
        if not isinstance(value, typ) or (typ is int and isinstance(value, bool)):
            out.append(
                f"E9: {tag} {key} must be {typ.__name__}, got {type(value).__name__}"
            )
    return out


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
    shape = _shape_errors("document", doc, DOC_SHAPES)
    if not shape and not all(isinstance(v, str) for v in doc.get("verticals") or []):
        shape.append("E9: document verticals must be a list of strings")
    if shape:
        return (errors + shape, warnings)

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
        shape = _shape_errors(tag, region, REGION_SHAPES)
        if not shape:
            if not all(
                s is None or isinstance(s, dict) for s in region.get("sources") or []
            ):
                shape.append(f"E9: {tag} sources entries must be mappings")
            if not isinstance(
                (region.get("evidence") or {}).get("row-counts") or {}, dict
            ):
                shape.append(f"E9: {tag} evidence row-counts must be dict")
        if shape:
            errors.extend(shape)
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
        if type(tier) is not int or not 1 <= tier <= 4:  # bool is not a tier
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
            if not isinstance(cat, str) or cat not in SOURCE_CATEGORIES:
                errors.append(f"E7: {tag} source category {cat!r} unknown")
            else:
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
                bad = [k for k, v in counts.items() if not (type(v) is int and v > 0)]
                if not counts or bad:
                    errors.append(
                        f"E6: {tag} row-counts must be non-empty and all > 0 "
                        f"(bad: {bad or 'empty'})"
                    )

    dark = [v for v in vocabulary if v not in seen]
    for v in dark:
        warnings.append(f"W1: vertical {v!r} is DARK (no region entry)")
    return (errors, warnings)


def _emit(line, stream=None):
    """Print one physical, bounded line: control characters escaped, length capped."""
    line = "".join(ch if ch.isprintable() else repr(ch)[1:-1] for ch in line)
    if len(line) > MAX_LINE:
        line = line[: MAX_LINE - len(TRUNCATED)] + TRUNCATED
    print(line, file=stream)


def main(argv, today=None):
    if len(argv) != 2:
        print("usage: validate_regions.py <regions.yaml>", file=sys.stderr)
        return 2
    try:
        with open(argv[1], "rb") as fh:
            data = fh.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            _emit(f"validate_regions: {argv[1]} exceeds {MAX_BYTES} bytes", sys.stderr)
            return 2
        doc = yaml.load(data, Loader=_NoAliasLoader)  # SafeLoader subclass
    # ValueError: a 5,000-digit integer or an unquoted impossible date (2026-13-45) raises
    # from PyYAML's constructors; RecursionError: deep nesting in the composer.
    except (OSError, yaml.YAMLError, ValueError, RecursionError) as exc:
        _emit(f"validate_regions: cannot read/parse {argv[1]}: {exc}", sys.stderr)
        return 2
    errors, warnings = validate(doc, today=today)
    for line in warnings:
        _emit(f"WARN  {line}")
    for line in errors:
        _emit(f"ERROR {line}")
    print(f"validate_regions: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
