# ADR 0001 — Layered knowledge base on a hardened second-brain fork

**Status:** ACCEPTED (operator sign-off 2026-09-02; bg-agent L0 writes CONDITIONED on the §5 OWASP pipeline)
**Date:** 2026-09-02
**Deciders:** operator + 4-lens data-science council (data-layer architecture, second-brain reconnaissance, drift/correctness/ML, governance/gate)
**Supersedes:** the interim "hand-authored vault only" posture recorded in `~/work/_graph/Graft-Fork.md`

## Context

The workspace needs a navigable knowledge base where AI can enrich and cross-link
content **without ever corrupting hand-authored precedent**. Two candidate tools
were assessed:

- **Graft** (`NanoNets/context-graph-engine`) parses **code only** (tree-sitter; no
  markdown grammar). It cannot graph a prose/lessons corpus — wrong vehicle for the
  knowledge layer. Kept as a gated, source-built **code**-navigation tool only
  (see `Graft-Fork.md`); out of scope here.
- **obsidian-second-brain** (`eugeniughelbur/obsidian-second-brain`) is a Claude Code
  skill that ingests sources and rewrites an Obsidian vault. Its value (auto-synthesis,
  cross-linking, embeddings) is wanted; its delivery (a `curl|bash` installer that writes
  `~/.claude/settings.json`, an unattended Telegram poller, direct multi-vendor API
  egress) violates this project's gates (Skill Security Gate / L21 auto-REJECT; Loop
  Launch Gate; no-direct-vendor-API posture).

**Decision driver:** keep the capability, contain the delivery — by *architecture*
(a data-layer boundary the tool physically cannot cross) plus a *hardened fork*
(the L27 remedy: reproduce a wanted capability through a trusted channel).

## Decision

### 1. Three-tier data hierarchy (writes only ever flow down)

| Tier | Contents | Sole writer | Fork's access |
|---|---|---|---|
| **L0 — immutable SSOT** | Hand-authored precedent: LESSONS/LEDGER, bok `decisions/instruments/hubs/frameworks/exceptions`, all `_graph/` notes, second-brain `raw/`. | **Human only** | **read-only** (prose) |
| **L1 — deterministic-derived** | Mechanically regenerated from a named SSOT by a **no-LLM** transform (bok `_state/`). Reproducible byte-for-byte modulo `generated-at`. | **`sync.py` only** (whole-file overwrite) | read-only |
| **L2 — AI-synthesized** | The fork's product: summaries, extracted patterns, embedding index, cross-link/backlink maps, contradiction flags. Second-brain `wiki/`. | **fork only** | read-write, **only here** |

**Invariant — prose flows down, links CRUD across all tiers (operator ruling 2026-09-02):**
- *Prose*: human→L0, `sync.py`→L1, fork→L2. Nothing writes another tier's prose.
- *Links*: the fork MAY create/update/delete wikilinks/backlinks **across all tiers**,
  but **only inside a delimited machine-owned block** (`<!-- L2:links start -->` …
  `<!-- L2:links end -->`) appended to a note. A tier's authored prose above the fence
  is never touched.

This is the operator's revision of the council's "L0 byte-frozen" default: the containment
guarantee is downgraded from *"the fork cannot alter a byte of SSOT"* to *"the fork alters
SSOT only inside the link fence."* The residual risk (a malformed write eating prose above
the fence) is mitigated by the fence-diff guard in §3.

### 2. LLM + embeddings + enrichment — AWS Bedrock only (no direct vendor API)

Operator ruling 2026-09-02: **all** model and embedding provisioning routes through AWS
Bedrock — no `api.anthropic.com`, no OpenAI/Grok/Perplexity/Gemini direct calls.

- **LLM** (summarize / synthesize / reconcile): Claude via **Bedrock** (short model ids +
  cross-region inference profile, matching the existing 242 setup — memory
  `reference_bedrock_chat_config`).
- **Embeddings**: **Bedrock** (Titan/Cohere), replacing both local Ollama and the remote
  OpenAI backend. Vectors are stored in **pgvector on the existing Throughline RDS**
  (operator ruling 2026-09-02) — **no OpenSearch Serverless / Bedrock Knowledge Bases
  standing cost**. The index is L2 derived data, never a source of truth; a retrieval hit
  is a SQL similarity query that must resolve to a real note path or be dropped
  (fail-closed).
- **Enrichment scope = curated + scholarly only** (operator ruling): retrieval over
  ingested sources via the **pgvector index** (Bedrock embeddings + SQL similarity — NOT
  Bedrock Knowledge Bases, to avoid the OpenSearch floor) + keyless public data fetches
  (arXiv, Crossref, OpenAlex, Semantic Scholar, Wikipedia) treated as **inert-data**
  WebFetch. **No live web search** (Grok/Perplexity/Tavily/Brave — stripped) and **no media
  transcription** (Whisper/podcast/YouTube — stripped).
- **Model tiering (cost control):** generation/synthesis → Claude **Sonnet** via Bedrock;
  the three LLM-based OWASP guard checks (§5) → **Haiku** (classifier tier, ~10× cheaper);
  human-gated L2→L0 promotion review may use Opus rarely. Per the Subagent-Model-Routing
  rule (route by ambiguity: bottom tier for classification).

### 3. Fork hardening (before it may ever run)

Modeled on the Graft `gate-hardening` precedent (`FORK_HARDENING.md`: no-op the offending
path, keep the signature, pin a red-first test as a merge gate).

**Strip (delete, not disable — a disabled path is one env-var from live):**
- Installer + config writers: `quick-install.sh`, `install.sh`, `setup.sh`,
  `setup_settings_hook.py`, `update.sh`. Replace with a manual, reviewed, source-built
  install (`--ignore-scripts`) that never writes `~/.claude/settings.json`.
- Unattended pollers: the `integrations/telegram-journal/` launchd daemon.
- Direct third-party egress: the `scripts/research/` web-search + LLM providers (Grok,
  Perplexity, Gemini, Tavily, Brave) and the `scripts/research/` media pipeline
  (yt-dlp/ffmpeg/Whisper). The **enrichment function is rebuilt on Bedrock KB** (§2), not
  deleted; the direct-API implementation is what's removed.
- Remote embed backend (`OBSIDIAN_EMBED_BACKEND=openai`) → Bedrock embeddings.

**Keep, scoped:**
- The PostCompact **bg-agent** (`obsidian-bg-agent.sh`, headless autonomous writer) —
  operator-retained. Its writes are pinned to the L2 root; any L0 link-block write passes
  the fence-diff guard (below). Its model calls route to Bedrock.
- The mutation scripts (`merge_notes.py`, `heal_links.py`, `triage_links.py`, …) — the
  link/vault CRUD — write only L2 + link fences.

**Enforce (fail-closed, defense-in-depth):**
1. **Write-root confinement**: one required `DERIVED_VAULT_ROOT`; unset → hard error (no
   cwd/`~` fallback). Every write routes through one guard that `realpath`-resolves the
   target and asserts it is inside L2 **or** inside a valid link fence in any tier.
2. **Fence-diff guard**: a machine write to an L0/L1 note must change bytes **only between
   the fence markers**; the guard diffs the file and rejects any change to prose outside
   the fence. This is the containment for the operator's link-CRUD model.
3. **OS backstop**: run the fork as a principal with **no write bit on the SSOT repos**
   except through the reviewed link-block path (the load-bearing control — survives a guard
   bug).
4. **`layer:` linter** (pre-commit + required CI): every note carries `layer: L0|L1|L2`;
   a tool-authored commit touching an `L0`/`L1` note outside its fence, or any note missing
   `layer:`, FAILS. A linter that parsed zero notes FAILS.
5. **Egress test** (CI, red-first): grep for any non-Bedrock model/host (`api.anthropic.com`,
   `api.x.ai`, `api.perplexity.ai`, `googleapis`, OpenAI, Ollama) → must be zero.

### 4. Provenance + drift control on L2 (reuses the bok stamp triad)

Every L2 note carries mandatory frontmatter; the producer refuses to emit one missing any
field (schema gate, fail-closed):

```yaml
layer: L2
type: synthesis | pattern | crosslink | contradiction | embedding-index
source-refs: [ "LESSONS.md#lesson-16", "decisions/D-0017.md" ]   # required, non-empty
source-hashes: { "decisions/D-0017.md": "sha256:…" }             # SSOT hash at generation
generated-by: second-brain-fork@<commit>
generated-at: 2026-09-02T13:00:00Z
model: bedrock/<model-id> | bedrock-embed/<id>
confidence: high | med | low          # driven by source-resolution, not model self-report
unverified: true                       # never absent on an L2 note
updated: 2026-09-02
source-verified: 2026-09-02            # last time source-refs confirmed present + hash-matched
stale-after: 30                        # days (contradiction flags: 7)
review-status: unreviewed | promoted
```

- **Drift = content-hash, not just time**: on each sync, hash the current SSOT source vs
  the stored `source-hashes`; mismatch ⇒ the L2 note is stale by construction, auto-quarantined
  (dropped from graph + retrieval), never silently rewritten.
- **Promotion L2→L0 is a human event only** — a person copies content into an L0 note,
  strips `layer`/`unverified`, stamps `source-verified`. No machine process creates or edits
  an `L0` note's prose.
- **L24 guard**: an L2 claim stronger than its cited source is a drift finding, not a paraphrase.

### 5. OWASP GenAI LLM Top-10 (2026 v1.0) processing pipeline — MANDATORY gate on autonomous L0 writes

Operator ruling 2026-09-02: the autonomous bg-agent MAY write L0 link-fences, but **only
if every autonomous write first passes a processing pipeline covering the OWASP Top 10 for
LLM Applications 2026** (source: `OWASP-GenAI-LLM-Top-10-2026-v1.0.pdf`, dated 2026-08-04).
The pipeline is a **fail-closed pre-write gate**: bg-agent generates → pipeline runs all ten
checks → the write commits (to L2, or an L0/L1 link-fence) only on a clean pass; any check
failing quarantines the candidate write to L2 `_review/` for a human and never touches L0.
The gate is heaviest on L0-targeted writes (the SSOT-mutation path); L2-only writes run the
same checks but a failure just quarantines within L2.

| # (2026) | Risk | Control in the bg-agent → L0 pipeline |
|---|---|---|
| LLM01 | Prompt Injection (incl. cross-modal) | Ingested content (raw/, compaction summaries, any image/audio in scope) is INERT data: instruction-shaped spans are neutralized, never executed; the generator prompt hard-separates data from instructions; cross-modal inputs are excluded unless a scanner clears them. |
| LLM02 | Sensitive Information Disclosure | Secret/PII scan (reuse `secret-scanner.sh` patterns) on every generated fence/note before write; an L2 note or link-fence carrying a credential/PII pattern is blocked. SSOT secrets never propagate into derived text. |
| LLM03 | Excessive Agency | The bg-agent's authority is minimized: tool surface capped to Read/Write/Edit (no Bash/network), write-root confined to L2 + valid link-fences, fence-diff guard on any L0 write, promotion L2→L0 human-only. The autonomy itself is the risk this row contains. |
| LLM04 | Supply Chain | Fork is source-built (`--ignore-scripts`), pinned commit, dep-audited; the strip tests are required merge gates (per §3). No packaged/installer path. |
| LLM05 | Data & Model Poisoning | No fine-tuning (Bedrock base models only); source provenance via `source-hashes`; a source whose hash changed quarantines its derivations (drift, §4). |
| LLM06 | Unbounded Consumption | Loop Launch Gate on the bg-agent: hard iteration cap, token/$ budget cap, and an escalation path declared before it runs; per-run write count bounded. |
| LLM07 | Misinformation | Provenance + confidence + `unverified:` on every L2 note; regenerate-and-diff; the L24 strength-escalation check flags a claim stronger than its source. Low source-resolution ⇒ auto-quarantine. |
| LLM08 | Hidden Context Exposure | Context isolation: generated notes/fences never embed system prompt, hidden instructions, or out-of-scope SSOT context; output scanned for leaked context markers before write. |
| LLM09 | Vector & Embedding Weaknesses | The Bedrock embedding index is derived/regenerable, access-scoped; retrieval hits must resolve to a real note path (fail-closed); sensitive folders excluded from embedding to prevent inversion exposure of SSOT. |
| LLM10 | Improper Output Handling | Generated markdown is sanitized before commit: no injected HTML/script, well-formed frontmatter, fence-marker integrity; the `layer:` linter + fence-diff guard validate the write. This is the last gate before bytes land in a note. |

Each row ships with a red-first test (a poisoned candidate that MUST be blocked + a clean one
that MUST pass), wired into CI as a merge gate — the enforcement without which this ADR is
prose (L17). The pipeline is itself an LLM-processing surface, so it runs on Bedrock under the
same egress pin (§2), and its own prompts are covered by the LLM01/LLM08 controls.

## Consequences

**Positive:** enrichment/synthesis capability retained; SSOT prose provably immutable
(fence-diff + OS backstop); single cloud (Bedrock) = one IAM/egress surface matching
existing infra; provenance makes every derived note traceable + regenerable; the whole
thing reuses the bok fail-closed stamp/sync machinery.

**Cost profile (AWS, list-price estimate — verify current Bedrock pricing):** usage-driven,
**no standing floor** (pgvector reuses existing RDS; no OpenSearch/KB). Generation dominates
at ~$0.60/bg-agent run (Sonnet); Haiku guard checks add ~$0.03/run; embeddings negligible.
Monthly ≈ **$20–30 light / $200–300 moderate / $1,000–1,500 heavy** (per-compaction across
many sessions). The Loop Launch Gate budget cap (§5 LLM06) bounds the heavy tail.

**Negative / accepted:** a recurring **fork re-audit tax** (each upstream pull re-checks for
reintroduced installer/egress/pollers — heavier than Graft because these are near
second-brain's core); **pin-and-rarely-upgrade** required; the kept bg-agent + link-CRUD
into L0 fences is a real (bounded) mutation surface, not zero; no live web search or media
transcription.

**Open sign-off items (schema is taste-grained per L27):** the `layer:`/provenance
frontmatter field names; the fence-marker syntax; the `DERIVED_VAULT_ROOT` layout; whether
the bg-agent may write link-fences into L0 at all or only into L2 (the residual-risk knob).
