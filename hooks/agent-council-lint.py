#!/usr/bin/env python3
"""agent-council-lint.py -- enforces Subagent Model Routing and the Infra Council Gate's
record format (LESSONS Lesson 30). Run in an adopter repo's CI:

    python3 agent-council-lint.py [--allow-empty] [ROOT]

Agents (ROOT/.claude/agents/**/*.md):
  A1  YAML frontmatter present, parseable, a mapping
  A2  `model:` declared (un-set = inherit = parent rates, the routing defect)
  A3  `model:` is an alias (opus, sonnet, haiku, fable, inherit) or a full claude-* id

Council records (ROOT/docs/council/YYYY-MM-DD-<topic>.md):
  C1  filename is YYYY-MM-DD-<topic>.md
  C2  YAML frontmatter present, parseable, a mapping, with topic, date, author_model,
      refuter, lenses, verdict
  C3  `date` equals the filename's date
  C4  `lenses` is a list of {lens, model}; the four required lenses are present
  C5  every model (lenses and author_model) maps to a known family; `inherit` is not a
      model a record can name
  C6  the lenses span at least two families, or `single_family_reason` says why not
  C7  `refuter` names a lens whose family differs from the author's, unless
      `single_family_reason` is set
  C8  `verdict` is approve, reject or approve-with-conditions
  C9  `## Disagreements` and `## Rejected` sections exist and are not empty

ZERO: no agent files and no council records is an error unless --allow-empty, so a
mis-pointed ROOT cannot read as a pass. Output: one `path:RULE:message` line per error,
sorted, control characters escaped, at most MAX_LINE characters. Exit 1 on any error,
0 otherwise, 2 on usage. Stdlib + PyYAML only.
"""

import re
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("agent-council-lint: PyYAML required (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

MAX_BYTES = 262_144
MAX_LINE = 240
TRUNCATED = "...<truncated>"
MODEL_ALIASES = {"opus", "sonnet", "haiku", "fable", "inherit"}
CLAUDE_ID_RE = re.compile(r"^claude-[a-z0-9][a-z0-9.-]*$")
REQUIRED_LENSES = {
    "reliability-observability",
    "security-iam",
    "iac-delivery",
    "cost-operations",
}
REQUIRED_KEYS = ("topic", "date", "author_model", "refuter", "lenses", "verdict")
VERDICTS = {"approve", "reject", "approve-with-conditions"}
COUNCIL_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-[a-z0-9][a-z0-9-]*\.md$")
SECTION_RE = re.compile(r"^## (Disagreements|Rejected)[ \t]*$", re.M)
# Provider segment of a hosted inference id (eu.anthropic.claude-..., meta.llama3-...).
PROVIDER_RE = re.compile(
    r"^(?:(?:us|eu|apac|global)\.)?(anthropic|meta|mistral|amazon|cohere|deepseek)\."
)
# Family by id prefix. An unknown prefix is an error (C5): admitting a model family
# changes this table and the test that pins it.
FAMILY_PREFIXES = (
    ("claude-", "anthropic"),
    ("gemini-", "google"),
    ("gpt-", "openai"),
    ("o1", "openai"),
    ("o3", "openai"),
    ("o4", "openai"),
    ("mistral", "mistral"),
    ("pixtral", "mistral"),
    ("codestral", "mistral"),
    ("llama", "meta"),
)


def model_family(model):
    """Provider family of a model id or alias, or None when it is not known."""
    if not isinstance(model, str):
        return None
    m = model.strip().lower()
    if m in MODEL_ALIASES - {"inherit"}:
        return "anthropic"
    hosted = PROVIDER_RE.match(m)
    if hosted:
        return hosted.group(1)
    for prefix, family in FAMILY_PREFIXES:
        if m.startswith(prefix):
            return family
    return None


class _NoAliasLoader(yaml.SafeLoader):
    """SafeLoader that refuses aliases: they bound nothing a record needs and are the
    cheapest way to exhaust a parser (LESSONS Lesson 29)."""

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise yaml.YAMLError("YAML aliases (*name) are not allowed")
        return super().compose_node(parent, index)


def _short(value):
    r = repr(value)
    return r if len(r) <= 60 else r[:60] + TRUNCATED


def _frontmatter(path, errors, rule):
    """(mapping, body) from a file's YAML frontmatter, or (None, None) after an error."""
    with open(path, "rb") as fh:
        data = fh.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        errors.append((path, rule, f"file exceeds {MAX_BYTES} bytes"))
        return None, None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        errors.append((path, rule, "not valid UTF-8"))
        return None, None
    parts = re.match(
        r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(.*)\Z", text, re.S
    )
    if not parts:
        errors.append((path, rule, "no YAML frontmatter block"))
        return None, None
    try:
        meta = yaml.load(parts.group(1), Loader=_NoAliasLoader)
    except (yaml.YAMLError, ValueError, RecursionError) as exc:
        errors.append((path, rule, f"frontmatter does not parse: {type(exc).__name__}"))
        return None, None
    if not isinstance(meta, dict):
        errors.append((path, rule, "frontmatter is not a mapping"))
        return None, None
    return meta, parts.group(2)


def check_agent(path, errors):
    meta, _ = _frontmatter(path, errors, "A1")
    if meta is None:
        return
    if "model" not in meta:
        errors.append(
            (path, "A2", "no model: declared (un-set inherits the parent's rates)")
        )
        return
    model = meta["model"]
    if not isinstance(model, str) or not (
        model in MODEL_ALIASES or CLAUDE_ID_RE.match(model)
    ):
        errors.append(
            (path, "A3", f"model {_short(model)} is not an alias or a claude-* id")
        )


def _sections(body):
    """{heading: stripped text} for the two dissent sections that are present."""
    found = {}
    matches = list(SECTION_RE.finditer(body))
    for m in matches:
        end = len(body)
        nxt = re.search(r"^#{1,2} ", body[m.end() :], re.M)
        if nxt:
            end = m.end() + nxt.start()
        found[m.group(1)] = body[m.end() : end].strip()
    return found


def check_council(path, errors):
    name = COUNCIL_NAME_RE.match(path.name)
    if not name:
        errors.append((path, "C1", "filename must be YYYY-MM-DD-<topic>.md"))
    meta, body = _frontmatter(path, errors, "C2")
    if meta is None:
        return
    missing = [k for k in REQUIRED_KEYS if k not in meta]
    if missing:
        errors.append((path, "C2", f"missing keys: {', '.join(missing)}"))
        return
    when = meta["date"]
    when = when.isoformat() if isinstance(when, date) else when
    if name and when != name.group(1):
        errors.append((path, "C3", f"date {_short(when)} does not match the filename"))

    lenses = meta["lenses"]
    if not isinstance(lenses, list) or not all(
        isinstance(x, dict)
        and isinstance(x.get("lens"), str)
        and isinstance(x.get("model"), str)
        for x in lenses
    ):
        errors.append((path, "C4", "lenses must be a list of {lens, model} strings"))
        return
    names = {x["lens"] for x in lenses}
    absent = sorted(REQUIRED_LENSES - names)
    if absent:
        errors.append((path, "C4", f"required lenses absent: {', '.join(absent)}"))

    author_family = model_family(meta["author_model"])
    if author_family is None:
        errors.append(
            (
                path,
                "C5",
                f"author_model {_short(meta['author_model'])} has no known family",
            )
        )
    families = set()
    for x in lenses:
        family = model_family(x["model"])
        if family is None:
            errors.append(
                (path, "C5", f"lens {_short(x['lens'])} model has no known family")
            )
        else:
            families.add(family)

    reason = meta.get("single_family_reason")
    disclosed = isinstance(reason, str) and reason.strip() != ""
    if len(families) < 2 and not disclosed:
        errors.append(
            (
                path,
                "C6",
                "lenses span one model family and single_family_reason is empty",
            )
        )
    refuter = [x for x in lenses if x["lens"] == meta["refuter"]]
    if not refuter:
        errors.append((path, "C7", f"refuter {_short(meta['refuter'])} is not a lens"))
    elif (
        not disclosed
        and author_family is not None
        and model_family(refuter[0]["model"]) == author_family
    ):
        errors.append((path, "C7", "refuter shares the author's model family"))

    if not isinstance(meta["verdict"], str) or meta["verdict"] not in VERDICTS:
        errors.append(
            (path, "C8", f"verdict must be one of {', '.join(sorted(VERDICTS))}")
        )

    sections = _sections(body)
    for heading in ("Disagreements", "Rejected"):
        if heading not in sections:
            errors.append((path, "C9", f"no '## {heading}' section"))
        elif not sections[heading]:
            errors.append((path, "C9", f"'## {heading}' is empty"))


def _line(root, path, rule, msg):
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    line = f"{rel}:{rule}:{msg}"
    line = "".join(ch if ch.isprintable() else repr(ch)[1:-1] for ch in line)
    return (
        line if len(line) <= MAX_LINE else line[: MAX_LINE - len(TRUNCATED)] + TRUNCATED
    )


def check(root, allow_empty=False):
    root = Path(root)
    agents_dir = root / ".claude" / "agents"
    agents = (
        sorted(p for p in agents_dir.rglob("*.md") if p.is_file())
        if agents_dir.is_dir()
        else []
    )
    council_dir = root / "docs" / "council"
    councils = (
        sorted(p for p in council_dir.glob("*.md") if p.is_file())
        if council_dir.is_dir()
        else []
    )
    errors = []
    if not agents and not councils and not allow_empty:
        errors.append(
            (
                root,
                "ZERO",
                "no .claude/agents/*.md and no docs/council/*.md (pass --allow-empty)",
            )
        )
    for path in agents:
        check_agent(path, errors)
    for path in councils:
        check_council(path, errors)
    return (
        sorted(_line(root, p, r, m) for p, r, m in errors),
        len(agents),
        len(councils),
    )


def main(argv):
    args = argv[1:]
    allow_empty = "--allow-empty" in args
    args = [a for a in args if a != "--allow-empty"]
    if len(args) > 1 or any(a.startswith("-") for a in args):
        print("usage: agent-council-lint.py [--allow-empty] [ROOT]", file=sys.stderr)
        return 2
    lines, n_agents, n_councils = check(args[0] if args else ".", allow_empty)
    for line in lines:
        print(line)
    print(
        f"agent-council-lint: {n_agents} agent(s), {n_councils} council record(s), "
        f"{len(lines)} error(s)",
        file=sys.stderr,
    )
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
