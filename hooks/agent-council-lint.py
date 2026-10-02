#!/usr/bin/env python3
"""agent-council-lint.py -- enforces Subagent Model Routing and the Infra Council Gate's
record format (LESSONS Lesson 30). Run in an adopter repo's CI:

    python3 agent-council-lint.py [--allow-empty] [ROOT]
    python3 agent-council-lint.py --council FILE   # one record, as infra-council-guard.sh does

Agents (ROOT/.claude/agents/**/*.md). The `model:` line is read line by line, the way a
working agent file is read, so a field this lint does not check (an unquoted ": " in
`description`, say) never fails it:
  A1  a frontmatter block is present and the file is UTF-8
  A2  a top-level `model:` line is present (un-set = inherit = parent rates)
  A3  declared once, as one token with nothing after it (an inline comment is read as part
      of the model name and breaks agent launch), naming an alias (opus, sonnet, haiku,
      fable, opusplan, inherit; optionally [1m]) or an Anthropic model id
      (claude-*, a hosted anthropic.* id, claude-*@date)

Council records (ROOT/docs/council/**/YYYY-MM-DD-<topic>.md), strict YAML frontmatter:
  C1  filename is YYYY-MM-DD-<topic>.md with a real date
  C2  frontmatter parses to a mapping; topic, date, author_model, refuter, lenses and
      verdict are present, and the string fields are non-empty
  C3  `date` equals the filename's date
  C4  `lenses` is a list of {lens, model} with unique names, including the four required
  C5  every model (lenses and author_model) maps to a known family; `inherit` is not a
      model a record can name
  C6  the lenses span at least two families, or `single_family_reason` says why not
  C7  `refuter` names a lens on a different family from the author's; waived only when
      every lens shares one family and the reason is given
  C8  `verdict` is approve, reject or approve-with-conditions
  C9  `## Disagreements` and `## Rejected` each appear once, outside code fences, with
      real text (not a placeholder, comment, sub-heading or whitespace)

README.md and files starting with "_" are skipped in both trees. ZERO: no agent files and
no council records is an error unless --allow-empty, so a mis-pointed ROOT cannot read as
a pass. Files are decoded as UTF-8 with an optional BOM and CRLF normalised. Output: one
`path:RULE:message` line per error, sorted, control characters escaped, at most MAX_LINE
characters. Exit 1 on any error, 0 otherwise, 2 on usage. Stdlib + PyYAML only.
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
MODEL_ALIASES = {"opus", "sonnet", "haiku", "fable", "opusplan", "inherit"}
# One token: what follows `model:` when nothing else is on the line.
MODEL_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/\[\]-]*")
MODEL_LINE_RE = re.compile(r"^model[ \t]*:(.*)$", re.M)
REQUIRED_LENSES = {
    "reliability-observability",
    "security-iam",
    "iac-delivery",
    "cost-operations",
}
REQUIRED_KEYS = ("topic", "date", "author_model", "refuter", "lenses", "verdict")
STRING_KEYS = ("topic", "author_model", "refuter", "verdict")
VERDICTS = {"approve", "reject", "approve-with-conditions"}
COUNCIL_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})-[a-z0-9][a-z0-9-]*\.md")
SECTIONS = ("Disagreements", "Rejected")
PLACEHOLDERS = {"", "todo", "tbd", "none", "n/a", "na", "nil", "-", "--", "---", "..."}
# Hosted ids: an optional region (eu., us-gov., ...) then a provider segment.
PROVIDER_RE = re.compile(
    r"(?:(?:us|eu|apac|global|au|jp|ca|us-gov)\.)?"
    r"(anthropic|meta|mistral|amazon|cohere|deepseek|openai|google)\."
)
# Vendor paths (google/gemini-..., models/gemini-..., publishers/google/models/...).
VENDOR_PATH_RE = re.compile(
    r"(?:publishers/[a-z0-9-]+/models/|models/|"
    r"(google|openai|meta-llama|mistralai|anthropic|deepseek-ai)/)"
)
VENDOR_FAMILY = {
    "meta-llama": "meta",
    "mistralai": "mistral",
    "deepseek-ai": "deepseek",
}
# Family by id shape, each anchored on a boundary. An unknown id is an error (C5):
# admitting a model family changes this table and the test that pins it.
FAMILY_PATTERNS = (
    (re.compile(r"claude-"), "anthropic"),
    (re.compile(r"(?:gemini|gemma)-"), "google"),
    (re.compile(r"(?:chat)?gpt-|o\d+(?:-|$)"), "openai"),
    (
        re.compile(
            r"(?:mistral|mixtral|ministral|magistral|devstral|codestral|pixtral)(?:-|$)"
        ),
        "mistral",
    ),
    (re.compile(r"llama[-\d]"), "meta"),
    (re.compile(r"deepseek-"), "deepseek"),
)


def model_family(model):
    """Provider family of a model id or alias, or None when it is not known."""
    if not isinstance(model, str):
        return None
    m = re.sub(r"\[1m\]$", "", model.strip().lower())
    if m in MODEL_ALIASES - {"inherit"}:
        return "anthropic"
    hosted = PROVIDER_RE.match(m)
    if hosted:
        return hosted.group(1)
    vendor = VENDOR_PATH_RE.match(m)
    if vendor:
        if vendor.group(1):
            return VENDOR_FAMILY.get(vendor.group(1), vendor.group(1))
        m = m[vendor.end() :]
    for pattern, family in FAMILY_PATTERNS:
        if pattern.match(m):
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


def _split(path, errors, rule):
    """(frontmatter text, body) of a file, or (None, None) after an error."""
    with open(path, "rb") as fh:
        data = fh.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        errors.append((path, rule, f"file exceeds {MAX_BYTES} bytes"))
        return None, None
    try:
        text = data.decode("utf-8-sig").replace("\r\n", "\n")
    except UnicodeDecodeError:
        errors.append((path, rule, "not valid UTF-8"))
        return None, None
    parts = re.match(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)(.*)\Z", text, re.S)
    if not parts:
        errors.append((path, rule, "no frontmatter block (--- ... ---) at the top"))
        return None, None
    return parts.group(1), parts.group(2)


def check_agent(path, errors):
    frontmatter, _ = _split(path, errors, "A1")
    if frontmatter is None:
        return
    lines = MODEL_LINE_RE.findall(frontmatter)
    if not lines:
        errors.append(
            (path, "A2", "no model: declared (un-set inherits the parent's rates)")
        )
        return
    if len(lines) > 1:
        errors.append((path, "A3", f"model: declared {len(lines)} times"))
        return
    raw = lines[0].strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1]
    if not MODEL_TOKEN_RE.fullmatch(raw):
        errors.append(
            (path, "A3", f"model {_short(raw)} is not one token (an inline comment?)")
        )
    elif raw != "inherit" and model_family(raw) != "anthropic":
        errors.append(
            (
                path,
                "A3",
                f"model {_short(raw)} is not an alias or an Anthropic model id",
            )
        )


def _sections(body):
    """{heading: [text, ...]} for the dissent sections, outside code fences."""
    body = re.sub(r"^(```|~~~).*?^\1[ \t]*$", "", body, flags=re.S | re.M)
    found = {}
    current = None
    for line in body.split("\n"):
        heading = re.match(r"(#{1,6})[ \t]+(.*?)[ \t#]*$", line)
        if heading:
            title = heading.group(2)
            if len(heading.group(1)) <= 2:
                current = (
                    title if heading.group(1) == "##" and title in SECTIONS else None
                )
                if current:
                    found.setdefault(current, []).append("")
            continue  # a sub-heading is structure, not content
        if current:
            found[current][-1] += line + "\n"
    return found


def _has_content(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t")
    words = re.sub(r"[\s.*_`>]+", " ", text).strip().lower()
    return words not in PLACEHOLDERS and re.search(r"\w", words) is not None


def check_council(path, errors):
    name = COUNCIL_NAME_RE.fullmatch(path.name)
    try:
        filename_date = date.fromisoformat(name.group(1)) if name else None
    except ValueError:
        filename_date = None
    if filename_date is None:
        errors.append(
            (path, "C1", "filename must be YYYY-MM-DD-<topic>.md with a real date")
        )
    frontmatter, body = _split(path, errors, "C2")
    if frontmatter is None:
        return
    try:
        meta = yaml.load(frontmatter, Loader=_NoAliasLoader)
    except (yaml.YAMLError, ValueError, RecursionError) as exc:
        errors.append((path, "C2", f"frontmatter does not parse: {type(exc).__name__}"))
        return
    if not isinstance(meta, dict):
        errors.append((path, "C2", "frontmatter is not a mapping"))
        return
    missing = [k for k in REQUIRED_KEYS if k not in meta]
    empty = [
        k
        for k in STRING_KEYS
        if k in meta and not (isinstance(meta[k], str) and meta[k].strip())
    ]
    if missing or empty:
        detail = [f"missing: {', '.join(missing)}"] if missing else []
        detail += [f"empty or not a string: {', '.join(empty)}"] if empty else []
        errors.append((path, "C2", "; ".join(detail)))
        return
    when = meta["date"]
    when = when.isoformat() if isinstance(when, date) else when
    if filename_date and when != filename_date.isoformat():
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
    names = [x["lens"] for x in lenses]
    repeated = sorted({n for n in names if names.count(n) > 1})
    if repeated:
        errors.append((path, "C4", f"lens named more than once: {', '.join(repeated)}"))
        return
    absent = sorted(REQUIRED_LENSES - set(names))
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
    single_family = len(families) < 2
    disclosed = single_family and isinstance(reason, str) and reason.strip() != ""
    if single_family and not disclosed:
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

    if meta["verdict"] not in VERDICTS:
        errors.append(
            (path, "C8", f"verdict must be one of {', '.join(sorted(VERDICTS))}")
        )

    sections = _sections(body)
    for heading in SECTIONS:
        texts = sections.get(heading, [])
        if not texts:
            errors.append(
                (path, "C9", f"no '## {heading}' section outside a code fence")
            )
        elif len(texts) > 1:
            errors.append((path, "C9", f"'## {heading}' appears {len(texts)} times"))
        elif not _has_content(texts[0]):
            errors.append((path, "C9", f"'## {heading}' has no real text"))


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


def _files(directory):
    if not directory.is_dir():
        return []
    return sorted(
        p
        for p in directory.rglob("*.md")
        if p.is_file() and p.name != "README.md" and not p.name.startswith("_")
    )


def check(root, allow_empty=False):
    root = Path(root)
    agents = _files(root / ".claude" / "agents")
    councils = _files(root / "docs" / "council")
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


USAGE = "usage: agent-council-lint.py [--allow-empty] [ROOT] | --council FILE"


def check_one_council(path):
    """Lint a single council record (infra-council-guard.sh runs this at apply time)."""
    path = Path(path)
    errors = []
    check_council(path, errors)
    return sorted(_line(path.parent, p, r, m) for p, r, m in errors)


def main(argv):
    args = argv[1:]
    if args[:1] == ["--council"]:
        if len(args) != 2 or not Path(args[1]).is_file():
            print(USAGE, file=sys.stderr)
            return 2
        lines = check_one_council(args[1])
        for line in lines:
            print(line)
        return 1 if lines else 0
    allow_empty = "--allow-empty" in args
    args = [a for a in args if a != "--allow-empty"]
    if len(args) > 1 or any(a.startswith("-") for a in args):
        print(USAGE, file=sys.stderr)
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
