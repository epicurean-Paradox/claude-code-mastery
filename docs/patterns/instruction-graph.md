# Pattern: Instruction Graph (operating-instruction corpus as instruments)

**Version:** 1.0.0
**Status:** Published 2026-10-17
**Reference implementation:** `patterns/instruction-graph/`
**Implementations pin:** `implements: instruction-graph@1` (major version)

## Problem

An agent's operating instructions -- the rules, lessons, gates, protocols and
objectives that govern how it works -- accrete as large hand-edited markdown
files. As the corpus grows, four failures set in, each with a known shape:

- **Precedence is prose.** Which rule wins when two conflict is resolved by
  reading order and inline asides ("project rules take precedence"), never by
  anything a machine can check. A contributor cannot query the authority order.
- **Enforcement is scattered and unverifiable.** The discipline "a lesson that
  is not a gate gets re-violated" is honored unevenly across hooks, CI jobs,
  scripts and memory. Nothing records which instruction is enforced by what, or
  whether that enforcer still fires. An instruction can claim it is enforced
  while the hook has been uninstalled -- the badge is not the outcome.
- **There is no deviation harness.** Config has fail-closed validators; the
  instruction corpus has none, so a malformed or self-contradictory rule ships.
- **Edits do not diff.** A monolithic file with very long lines (one paragraph
  per line) turns a one-word change into a hunk the size of the whole line. An
  LLM reviewer fed that diff can overflow its context window and fail, and if the
  review is a required check the change deadlocks.

The naive fixes fail: a hand-written "index of rules" drifts; deleting a
superseded rule destroys the record that the old wording was wrong, which is how
it gets re-violated; and reflowing the file alone leaves precedence and
enforcement as prose.

## Pattern

Decompose the corpus into **atomic, linked, indexed, validated
instruction-instruments**: one markdown file per instruction, prose body plus a
validated YAML frontmatter, related by typed directional links, checked by a
fail-closed validator that is itself a required gate.

### 1. Instruments as committed data

One file per instruction (`<id>.md`). The body stays prose -- instructions carry
nuance and rationale that resist schematizing, and the "why" is what stops
re-violation. The frontmatter is data (`id`, `title`, `layer`, `type`, `status`,
`enforcement`, `links`, provenance), validated `additionalProperties: false`.
Schema: `patterns/instruction-graph/instruction-graph.schema.md`.

Atomize at the unit that is independently **enforced, superseded, or cited**. A
block that is never any of these is narrative: keep it in a `type: narrative`
file, un-atomized. Over-atomization yields a link graph nobody curates and a pile
of stubs; the enforced/superseded/cited rule is the falsifiable bound.

### 2. Precedence as data

An ordered authority vocabulary (`layer`, e.g. `org-global > team > project >
session > memory`) is declared once and pinned by each implementation. The
validator resolves conflicts deterministically: two instruments that
`conflicts_with` each other at the same layer are an error unless an explicit
`supersedes` breaks the tie. Precedence stops being a sentence and becomes a
check.

### 3. Enforcement honesty: live, declared, absent

Every `rule`, `lesson` and `gate` names a **resolvable** enforcer as data, not a
prose claim: `enforcement: {kind, ref, state}`. The truth axis is `state`:

- `live` -- the enforcer runs in CI, so an implementation's binding test can
  exercise it against a violating fixture.
- `declared` -- a committed enforcer (e.g. a machine-local hook) that the in-repo
  validator confirms is present but cannot confirm fires. The honest middle
  state; claiming `live` for an enforcer that does not run in CI is the
  badge-is-not-the-outcome defect.
- `absent` -- none yet. `kind: none` forces `state: absent`, making "no
  enforcement is an open defect" machine-visible instead of prose.

This mirrors the observed-vs-declared axis of a knowledge graph: a claim is only
as strong as what a tool can confirm.

### 4. Typed links and the DAG

Links are directional verbs, not a flat list: `supersedes`, `refines`,
`derived_from` (a DAG -- the validator rejects cycles), plus `enforces`,
`enforced_by`, `conflicts_with` (exempt from the cycle check, because a
`conflicts_with` resolved by a `supersedes` is a legitimate cycle and a rule may
be refined by the enforcer it enforces). Every target resolves to a known
instrument, so an edge cannot dangle silently.

### 5. What the validator can and cannot check

Three distinct claims, only the first two mechanizable:

- **Well-formed** (config-invariant): the frontmatter obeys the schema. A
  markdown validator proves this by poisoning a fixture and asserting it errors.
- **Reference binds**: the named enforcer exists and reaches the rule. This is an
  implementation's own test (resolve `path::symbol` to a real definition; run the
  hook against a red fixture). The pattern's reference validator checks the
  reference is well-shaped and leaves binding to the implementation.
- **The agent obeyed**: not checkable by a validator at all -- a category error.
  It needs runtime hooks or an agent-eval harness. The instrument graph makes
  enforcement *visible and named*; it does not make obedience testable, and must
  not imply it does.

### 6. Generated layers are not hand-edited

A current-state summary (what is active, what is blocked) is **generated** from
instrument statuses and emitted wrapped at a bounded line length, never
hand-edited. This is what removes the giant-line-diff failure: a status change
re-emits one short line. Hand-editing a generated summary is forbidden the same
way hand-editing a regenerated knowledge-graph layer is.

### 7. Keeping public pattern and private implementation aligned

When the pattern is public and an implementation is private, symmetry by fiat
drifts. Mechanism instead:

- The public pattern owns the versioned spec (this document + schema +
  validator).
- Each private implementation pins `implements: instruction-graph@<major>` and
  fails CI when its pin is more than one release behind public latest.
- Authorship direction is the confidentiality control: author the public pattern
  from first principles, then instantiate privately. Never distill private
  material into the public repo and scrub afterward -- scrubbed mentions survive
  in history, PR bodies and reflogs.

## Reference implementation

`patterns/instruction-graph/` contains:

- `instruction-graph.schema.md` -- field-by-field schema of an instrument.
- `validate_instructions.py` -- fail-closed validator (stdlib + PyYAML only):
  schema conformance, additionalProperties, ordered-layer precedence, typed-link
  resolution + DAG acyclicity, enforcement shape, tombstones. Bounds its own
  inputs (bounded read, frontmatter cap, alias refusal) and output (one escaped
  line <=240 chars).
- `examples/acme-instruments/` -- a worked example for a fictional org ("Acme
  Metrics"): a protocol, a rule with a `live` enforcer, and a lesson with a
  `declared` one.
- `test_validate_instructions.py` -- red-first tests: every rule has a fixture
  that MUST fail and a clean fixture that MUST pass; the example MUST validate.

## Rejected alternatives

- **Reflow and split the monolith only** -- fixes the diff overflow at low cost
  but delivers no precedence resolution, no enforcement map and no deviation
  harness. A valid cheaper tier when only the diff problem bites; not this
  pattern.
- **Schematize the prose body into YAML** -- instructions are judgment, not data;
  forcing the body into scalars strips the rationale that prevents re-violation.
  Body stays markdown; only the frontmatter is data.
- **A presence-only `enforced_by` string** -- rebuilds the "no enforcement is an
  open defect" problem one level up. The `kind`/`ref`/`state` triple with a
  resolvable reference is the fix.
- **Deleting superseded instruments** -- destroys the correction trail. Withdrawn
  instruments stay as tombstones.
- **Claiming the graph tests obedience** -- a category error; the validator
  checks shape and reference, never that an agent followed a rule.
