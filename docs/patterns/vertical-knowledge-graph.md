# Pattern: Vertical Knowledge Graph (BOK operationalization)

**Version:** 1.0.0
**Status:** Published 2026-09-02
**Reference implementation:** `patterns/vertical-knowledge-graph/`
**Implementations pin:** `implements: vertical-knowledge-graph@1` (major version)

## Problem

An organization's operational knowledge arrives through many source systems (CRM,
ticketing, HR, VCS, conversation intelligence, product analytics). Each source is
ingested and consumed in isolation. Nobody — human or agent — can ask "what does the
organization know about revenue?" and get an answer that is scoped, access-controlled,
and honest about what is actually observed versus merely intended.

The naive fixes fail in known ways:

- A hand-written "system overview" document drifts within weeks and cannot be
  access-controlled at a finer grain than the file.
- A monolithic knowledge graph with no vertical structure gives every reader every
  edge, which makes HR-adjacent data the ceiling for who may read anything.
- A graph whose regions are declared but never verified ships aspiration as fact —
  the classic gap between "the pipeline exists" and "the pipeline ran yesterday and
  wrote rows".

## Pattern

Operationalize the Body of Knowledge (BOK) as **graph regions per business vertical**
(finance, product, people-ops, revenue, go-to-market, development, …), constituted
from sources the platform already ingests, each region carrying a machine-checkable
truth status and an access-control binding.

### 1. Region map as committed data

One committed YAML file (`regions.yaml`, schema in the reference implementation) is
the single source of truth for the graph's shape:

- `vertical` — which region a source/entity belongs to. Assignment is judgment
  (a conversation-intelligence source can feed both revenue and product) and
  therefore lives in the declared layer, reviewed like code.
- `sources` — the ingested systems feeding the region, by category (crm, ticketing,
  hr, vcs, …), never only by vendor name.
- `destinations` — the tables/collections the region's data lands in.
- `rbac` — the intended read scope for the region, plus an explicit
  `enforced: true|false` and, when true, the named enforcement point.
- `sensitivity_tier` — see §3.
- `consumers` — named humans/teams/agents with a recurring question this region
  answers. A region with no consumer is deferred, not built (see §5).

The region map is **declared** data (tier L0 in a layered knowledge base: reviewed,
human-accountable). Inventories derivable from live state — connector health, table
row counts, schema introspection — are **regenerated** data (tier L1: produced by
named deterministic tools, never hand-edited). Synthesis across regions is tier L2.

### 2. Truth protocol: observed vs declared-only

Every region carries `status: observed | declared-only`. `observed` is a claim and
must be paid for with evidence, all machine-checkable:

```yaml
status: observed
evidence:
  source-health: { crm: healthy@2026-09-02 }     # connector health check
  row-counts: { accounts: 1854 }                  # destination rows > 0
  last-run: { id: 4231, at: 2026-09-02T06:00Z }  # successful pipeline execution
  verified-at: 2026-09-02
  describes-commit: <sha>                         # repo state the claim describes
```

A region missing any probe defaults to `declared-only` and is excluded from every
"the system currently does X" statement. The validator fails a region that claims
`observed` without a complete evidence block. Freshness is part of truth: evidence
older than the region's `stale-after` window demotes the region to `declared-only`
at validation time, loudly.

### 3. Sensitivity tiers and edge inheritance

Rank verticals by exposure class, highest first — typically: HR/people data;
finance and customer-revenue data (including conversation-derived content, which
carries erasure obligations); product usage (pseudonymized); engineering internals.
Record the ranking in the region map (`sensitivity_tier: 1..4`, 1 highest).

Two rules make the ranking mean something:

- **A cross-vertical edge inherits the higher (more sensitive) tier of its
  endpoints.** A revenue-to-people edge is people-tier.
- **Conversation- or person-derived nodes carry erasure lineage** (which subject
  key deletes them), or they may not enter the graph. An erasure path that cannot
  reach a derived node is a silent compliance failure.

### 4. RBAC: label before enforcement, never claim enforcement early

Access control arrives in two stages, and the region map is honest about which
stage a region is in:

1. **Label now.** Every node/region carries its `vertical:` at write time,
   fail-closed (an unlabeled node never enters the graph). Read scopes use a
   vocabulary like `graph:read:<vertical>`.
2. **Enforce at one choke point.** All consult queries pass through a single
   resolver that filters by the caller's granted verticals; deny-by-default on
   unknown verticals (a query for an unregistered vertical returns empty, not all).

Until the enforcement point exists, `rbac.enforced: false` stays in the committed
map, and regions in the top sensitivity tiers do not serve to general audiences.
Declared-but-unenforced access control, labeled as such, is a roadmap; the same
thing claimed as enforced is a breach waiting to be discovered.

### 5. Consumption surfaces and the adoption gate

Build the surface users actually reach for. Field evidence repeatedly shows that
a dense, scannable per-vertical grid (sources × entities × freshness × status)
outperforms a conversational interface as the *human* surface; a query interface
(e.g. an MCP tool) is the *agent* surface. Gate each region on a named consumer
with a recurring question before building its surface; a region without one is
deferred with an explicit trigger, mirroring test-suite inclusion gates.

### 6. Keeping public pattern and private implementation aligned

When the pattern is public and an implementation is private, symmetry by fiat
drifts. Mechanism instead:

- The public pattern owns the versioned spec (this document + schema + validator).
- Each private implementation pins `implements: vertical-knowledge-graph@<major>`
  and runs a CI rule: pinned version more than one release behind public latest
  fails.
- Authorship direction is the confidentiality control: author the public pattern
  from first principles, then instantiate privately. Never distill private material
  into the public repo and scrub afterward — scrubbed mentions survive in history,
  PR bodies, and reflogs.

## Reference implementation

`patterns/vertical-knowledge-graph/` contains:

- `regions.schema.md` — field-by-field schema of `regions.yaml`.
- `validate_regions.py` — fail-closed validator (stdlib + PyYAML only): schema
  errors, `observed` without evidence, stale evidence, enforced-without-
  enforcement-point, unknown verticals, unlabeled regions.
- `examples/acme.regions.yaml` — a worked example for a fictional B2B SaaS
  ("Acme Metrics"): five constitutable regions, one thin, one dark.
- `test_validate_regions.py` — red-first tests: every rule has a fixture that MUST
  fail and a clean fixture that MUST pass.

## Rejected alternatives

- **Standalone graph store parallel to an existing source/schema catalog** — the
  same facts held twice drift twice; the graph must consume the catalog.
- **Byte-identical public/private documents** — impossible without leaking; the
  spec/implementation split above is the workable symmetry.
- **Hand-authored field-grain region claims before introspection tooling exists** —
  unverifiable snapshots; declared-only until the deterministic generator ships.
- **Chat as the primary human surface** — adoption evidence points the other way;
  grid first, query for agents.
