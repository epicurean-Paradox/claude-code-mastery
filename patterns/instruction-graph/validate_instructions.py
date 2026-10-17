#!/usr/bin/env python3
"""Fail-closed validator for the instruction-graph pattern (instruction-graph@1).

Instruments are markdown files with a `---`-fenced YAML frontmatter block. The
validator reads ONLY the frontmatter (the prose body never reaches the parser),
reads each file in a bounded chunk, refuses YAML aliases before any value is
built, builds the instrument set, and checks the schema and graph invariants.

It is the config-invariant half of the pattern: it proves an instrument is
well-formed and that its declared enforcement REFERENCE is shaped correctly.
Proving the reference BINDS (the named symbol exists, the hook fires) belongs to
an implementation's own test suite -- see test_validate_instructions.py, which
resolves each `path::symbol` reference to a real definition. A markdown validator
cannot check that an agent OBEYED an instruction; that is a category error and is
not claimed here.

Stdlib + PyYAML only; no DB, no network, no writes.

Rules:
  I1  frontmatter parses, is a mapping, carries the required keys, and declares
      no key outside the schema (additionalProperties: false)
  I2  layer is a string in the ordered authority vocabulary
  I3  type is a string in the type vocabulary
  I4  status is a string in the status vocabulary; superseded/withdrawn is a
      tombstone (names superseded_by / withdrawn_reason)
  I5  a rule/lesson/gate declares enforcement {kind, ref, state} with string
      kind/state in vocab; kind: none forces state: absent; a non-none kind
      needs a non-empty ref
  I6  id is a unique, identifier-shaped string
  I7  links is a mapping of known verb -> list of string ids; every target
      resolves to a known instrument id
  I8  the graph is acyclic over refines/supersedes/derived_from; a same-layer
      conflicts_with must be broken by an explicit supersedes
  I9  zero instruments parsed is an error (fail-closed)
  W1  an instrument with no links is reported ORPHAN (warning)
  W2  review older than review_stale_after_days is reported STALE (warning)

Exit codes: 0 pass (warnings allowed), 1 any error, 2 unreadable input.
Every output line is a single line of at most 240 characters with control
characters escaped.
"""

import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("validate_instructions: PyYAML required (pip install pyyaml)\n")
    sys.exit(2)

# Ordered by authority, highest first. The order is load-bearing: a same-layer
# conflict (I8) is the one the resolver cannot break without an explicit
# supersedes. Implementations pin their own layer names; these are the default.
LAYERS = ["org-global", "team", "project", "session", "memory"]
TYPES = {"rule", "lesson", "gate", "protocol", "objective", "narrative"}
STATUSES = {"active", "superseded", "withdrawn", "proposed"}
ENFORCED_TYPES = {"rule", "lesson", "gate"}
ENFORCEMENT_KINDS = {"hook", "ci", "test", "pre-pr-checklist", "none"}
ENFORCEMENT_STATES = {"live", "declared", "absent"}
DAG_LINKS = {"supersedes", "refines", "derived_from"}
EXEMPT_LINKS = {"enforces", "enforced_by", "conflicts_with"}
LINK_VERBS = DAG_LINKS | EXEMPT_LINKS
REQUIRED_KEYS = ("id", "title", "layer", "type", "status")
ALLOWED_KEYS = {
    "id",
    "title",
    "layer",
    "type",
    "status",
    "enforcement",
    "links",
    "owner",
    "applies_to",
    "source",
    "last_reviewed",
    "review_stale_after_days",
    "superseded_by",
    "withdrawn_reason",
}
ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,96}$")
MAX_FRONTMATTER_BYTES = 16 * 1024
MAX_READ_BYTES = 4 * MAX_FRONTMATTER_BYTES
MAX_LINE = 240


def _fmt(text):
    """Bound and escape one output line (pattern contract: single line, <=240
    chars, control characters escaped)."""
    s = "".join(
        ch if ch.isprintable() or ch == " " else repr(ch)[1:-1] for ch in str(text)
    )
    return s[:MAX_LINE]


def _contains_yaml_alias(text):
    """Return the first alias's anchor name, or None. Scans the event stream
    (yaml.parse with SafeLoader) WITHOUT constructing objects, so no expansion
    happens -- safe_load still EXPANDS aliases and a tiny alias file can reach
    gigabytes. Using safe_load for the actual parse (not yaml.load) keeps static
    analysers quiet. Token-aware: flow syntax does not bypass it and quoted prose
    is not flagged."""
    for event in yaml.parse(text, Loader=yaml.SafeLoader):
        if isinstance(event, yaml.events.AliasEvent):
            return event.anchor or "?"
    return None


def split_frontmatter(text):
    """Extract the YAML frontmatter from a file's content (which may be a bounded
    prefix). Returns the string between the opening and closing `---` fences, or
    None when there is no fenced block at the start or no closing fence in the
    window. Reads only up to the closing fence, so the body never reaches YAML."""
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            return "\n".join(out)
        out.append(line)
    return None


def load_instrument(path):
    """Parse one instrument file's frontmatter. Returns (dict, None) on success
    or (None, reason) -- never raises (the file is untrusted input)."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_READ_BYTES)
    except OSError as exc:
        return None, f"cannot read: {exc}"
    fm = split_frontmatter(raw.decode("utf-8", "replace"))
    if fm is None:
        return (
            None,
            f"no YAML frontmatter block within the first {MAX_READ_BYTES} bytes",
        )
    if len(fm.encode("utf-8")) > MAX_FRONTMATTER_BYTES:
        return None, f"frontmatter exceeds {MAX_FRONTMATTER_BYTES} bytes"
    try:
        alias = _contains_yaml_alias(fm)
        if alias is not None:
            return None, f"YAML aliases are not permitted (expansion bomb): *{alias}"
        data = yaml.safe_load(fm)
    except yaml.YAMLError as exc:
        return None, f"frontmatter is not valid YAML: {exc}"
    if not isinstance(data, dict):
        return None, "frontmatter is not a mapping"
    return data, None


def enforcement_problem(enf):
    """None when the enforcement block is well-formed, else the I5 reason. A
    non-mapping or a non-string/collection-valued kind or state is a reason,
    never a crash."""
    if not isinstance(enf, dict):
        return "enforcement must be a mapping with kind, ref and state"
    kind, state = enf.get("kind"), enf.get("state")
    if not isinstance(kind, str) or kind not in ENFORCEMENT_KINDS:
        return f"enforcement.kind {kind!r} not in {sorted(ENFORCEMENT_KINDS)}"
    if not isinstance(state, str) or state not in ENFORCEMENT_STATES:
        return f"enforcement.state {state!r} not in {sorted(ENFORCEMENT_STATES)}"
    if kind == "none" and state != "absent":
        return (
            "enforcement.kind none requires state absent (no enforcement = open defect)"
        )
    if kind != "none" and not (isinstance(enf.get("ref"), str) and enf["ref"].strip()):
        return f"enforcement.kind {kind} requires a non-empty ref"
    return None


def _links(fm):
    """Declared links as {verb: [str, ...]}, keeping only known verbs with a list
    of string targets (malformed shapes are reported by the I7 check)."""
    links = fm.get("links")
    if not isinstance(links, dict):
        return {}
    out = {}
    for verb, targets in links.items():
        if verb in LINK_VERBS and isinstance(targets, list):
            out[verb] = [t for t in targets if isinstance(t, str)]
    return out


def _has_cycle(nodes, edges):
    """True if the directed graph has a cycle. Iterative three-colour DFS so a
    deep chain cannot blow the stack."""
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {n: WHITE for n in nodes}
    for root in nodes:
        if colour[root] != WHITE:
            continue
        stack = [(root, iter(edges.get(root, ())))]
        colour[root] = GREY
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if nxt not in colour:
                    continue
                if colour[nxt] == GREY:
                    return True
                if colour[nxt] == WHITE:
                    colour[nxt] = GREY
                    stack.append((nxt, iter(edges.get(nxt, ()))))
                    advanced = True
                    break
            if not advanced:
                colour[node] = BLACK
                stack.pop()
    return False


def validate(instruments, today=None, layers=None):
    """Validate parsed instruments. `instruments` is a list of (path, dict);
    `layers` overrides the default authority vocabulary. Returns (errors,
    warnings)."""
    today = today or datetime.now(timezone.utc).date()
    layers = layers or LAYERS
    errors, warnings = [], []

    if not instruments:
        return (["I9: zero instruments parsed (fail-closed)"], [])

    ids, by_id = {}, {}
    for path, fm in instruments:
        if not isinstance(fm, dict):
            errors.append(f"I1: {path} frontmatter is not a mapping")
            continue
        tag = fm.get("id") or path
        missing = [k for k in REQUIRED_KEYS if not fm.get(k)]
        if missing:
            errors.append(f"I1: {tag} missing required keys {missing}")
        extra = sorted(set(fm) - ALLOWED_KEYS)
        if extra:
            errors.append(
                f"I1: {tag} has keys outside the schema {extra} (additionalProperties: false)"
            )

        iid = fm.get("id")
        if isinstance(iid, str) and ID_RE.match(iid):
            if iid in ids:
                errors.append(f"I6: duplicate id {iid!r} ({path} and {ids[iid]})")
            ids[iid] = path
            by_id[iid] = fm
        elif iid is not None:
            errors.append(f"I6: {tag} id {iid!r} is not an identifier-shaped string")

        layer = fm.get("layer")
        if not isinstance(layer, str) or layer not in layers:
            errors.append(f"I2: {tag} layer {layer!r} not in {layers}")
        itype = fm.get("type")
        if not isinstance(itype, str) or itype not in TYPES:
            errors.append(f"I3: {tag} type {itype!r} not in {sorted(TYPES)}")
        status = fm.get("status")
        if not isinstance(status, str) or status not in STATUSES:
            errors.append(f"I4: {tag} status {status!r} not in {sorted(STATUSES)}")
        if status == "superseded" and not fm.get("superseded_by"):
            errors.append(f"I4: {tag} superseded without superseded_by (tombstone)")
        if status == "withdrawn" and not fm.get("withdrawn_reason"):
            errors.append(f"I4: {tag} withdrawn without withdrawn_reason (tombstone)")

        if isinstance(itype, str) and itype in ENFORCED_TYPES:
            problem = enforcement_problem(fm.get("enforcement"))
            if problem:
                errors.append(f"I5: {tag} ({itype}) {problem}")

        declared = fm.get("links")
        links = _links(fm)
        if declared is not None and not isinstance(declared, dict):
            errors.append(f"I7: {tag} links must be a mapping of verb -> [id]")
        elif isinstance(declared, dict):
            for verb, targets in declared.items():
                if verb not in LINK_VERBS:
                    errors.append(f"I7: {tag} unknown link verb {verb!r}")
                elif not isinstance(targets, list):
                    errors.append(
                        f"I7: {tag} link {verb!r} targets must be a list of ids"
                    )
                elif any(not isinstance(t, str) for t in targets):
                    errors.append(f"I7: {tag} link {verb!r} has a non-string target")
        if not links and (not isinstance(declared, dict) or not declared):
            warnings.append(f"W1: {tag} is an ORPHAN (no links)")

        window = fm.get("review_stale_after_days")
        reviewed = fm.get("last_reviewed")
        if isinstance(window, int) and reviewed is not None:
            try:
                rd = (
                    reviewed
                    if isinstance(reviewed, date)
                    else datetime.strptime(str(reviewed)[:10], "%Y-%m-%d").date()
                )
                if (today - rd).days > window:
                    warnings.append(
                        f"W2: {tag} review is STALE (last {rd}, window {window}d)"
                    )
            except (ValueError, TypeError):
                errors.append(f"I1: {tag} last_reviewed is unparseable")

    dag_edges = {}
    for path, fm in instruments:
        if not isinstance(fm, dict):
            continue
        iid = fm.get("id")
        if not (isinstance(iid, str) and ID_RE.match(iid)):
            continue
        tag = iid
        links = _links(fm)
        dag_edges[iid] = []
        for verb, targets in links.items():
            for target in targets:
                if target not in by_id:
                    errors.append(
                        f"I7: {tag} {verb} target {target!r} resolves to no instrument"
                    )
                elif verb in DAG_LINKS:
                    dag_edges[iid].append(target)
        for target in links.get("conflicts_with", []):
            other = by_id.get(target)
            if other and other.get("layer") == fm.get("layer"):
                supersedes = set(links.get("supersedes", []))
                other_supersedes = set(_links(other).get("supersedes", []))
                if target not in supersedes and iid not in other_supersedes:
                    errors.append(
                        f"I8: {tag} conflicts_with {target!r} at the same layer with no supersedes resolving it"
                    )

    if _has_cycle(list(dag_edges), dag_edges):
        errors.append(
            "I8: a cycle exists over refines/supersedes/derived_from (must be a DAG)"
        )

    return (errors, warnings)


def load_dir(instruments_dir):
    """Load every `*.md` (except README.md) under a directory. Returns
    (instruments, load_errors)."""
    instruments, load_errors = [], []
    for path in sorted(Path(instruments_dir).glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        fm, problem = load_instrument(path)
        if problem:
            load_errors.append(f"I1: {path}: {problem}")
        else:
            instruments.append((str(path), fm))
    return instruments, load_errors


def main(argv):
    """CLI: validate_instructions.py <instruments dir>. Exit 0 pass, 1 error,
    2 unreadable input."""
    if len(argv) != 2:
        sys.stderr.write("usage: validate_instructions.py <instruments dir>\n")
        return 2
    target = Path(argv[1])
    if not target.is_dir():
        sys.stderr.write(
            _fmt(f"validate_instructions: not a directory: {target}") + "\n"
        )
        return 2
    instruments, load_errors = load_dir(target)
    errors, warnings = validate(instruments)
    errors = load_errors + errors
    for line in warnings:
        print("WARN  " + _fmt(line))
    for line in errors:
        print("ERROR " + _fmt(line))
    print(
        _fmt(
            f"validate_instructions: {len(instruments)} instrument(s), "
            f"{len(errors)} error(s), {len(warnings)} warning(s)"
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
