# Examples

Real scenarios showing each pillar in action.

---

## 1. Layered Configuration

### Problem: Config Sprawl

One CLAUDE.md trying to cover a Slack bot AND a data pipeline:

```markdown
# CLAUDE.md (everything in one file)

- Verify Slack webhook signatures before processing
- Use pipeline orchestrator pattern, no standalone scripts
- Rate limit per user/channel
- All KPI queries must use materialized views
- Ghost theme: use {{#foreach}} not {{#each}}
- Pin npm dependencies
- Dark mode mandatory for all pages
```

Claude sees "Ghost theme" rules when working on the Slack bot. It wastes context and occasionally applies wrong rules to wrong code.

### Fix: Layer It

```
~/.claude/CLAUDE.md          → "Be direct. No emojis. Challenge assumptions."
~/CLAUDE.md                  → "Pin dependencies. Use HTTPS. Validate env vars at startup."
~/slack-bot/CLAUDE.md        → "Verify webhook signatures. Rate limit per user."
~/data-pipeline/CLAUDE.md    → "Pipeline orchestrator pattern. Verify row counts."
~/ghost-theme/CLAUDE.md      → "Use {{#foreach}}. Dark mode mandatory."
```

Each project gets exactly the rules it needs. Global standards apply everywhere without repetition.

---

## 2. Session Continuity

### Problem: Blind Continuation

Session 1 hits context limit after implementing a database migration. Summary says:

> "Worked on database changes. Some tables were modified."

Session 2 starts with no idea which tables, what state the migration is in, or what's next.

### Fix: Structured Handoff

Session 1's summary, forced by the continuity protocol:

```
=== CONTINUATION START ===
Before continuing:
1. Read HANDOFF.md
2. Read PROJECT_PLAN.md (Phase 2: Data Import)
3. State phase, blockers, next task
=== END ===

## What was done:
- Created migration 003_add_kpi_scores.sql
- Applied to dev database: 4 tables created (kpi_scores, kpi_thresholds, kpi_history, kpi_audit)
- Verified: SELECT COUNT(*) FROM kpi_scores → 0 rows (empty, ready for import)

## What's next:
- Implement KPI calculation stage in pipeline
- Blocker: threshold values need product team sign-off

## Verification state:
- Migration: applied ✓
- Tables exist: verified ✓
- Pipeline stage: not started
```

Session 2 reads HANDOFF.md, states "Phase 2, KPI calculation stage, blocked on threshold values" — and picks up exactly where Session 1 left off.

---

## 3. Session Decay

### Problem: Rule Erosion

Turn 1-10: Claude follows architecture rules, checks the plan, uses proper patterns.

Turn 15: Claude starts writing standalone scripts instead of pipeline stages.

Turn 25: Claude stops checking docs entirely and free-styles the implementation.

### Fix: Decay Prevention Trigger

```markdown
Every 10 responses OR when switching tasks:
1. Re-read PROJECT_PLAN.md current phase
2. Verify alignment with priorities
3. If drifted: "Refocusing on [X] per project plan"
```

At turn 10, Claude re-reads the plan. At turn 20, it does it again. At turn 25, when switching from backend to frontend work, it catches that the plan says "backend first" and flags the drift.

**Before decay prevention:**
> *Turn 22: "Here's the React component for the dashboard..."*
> (Nobody asked for frontend. The plan says finish the API first.)

**After decay prevention:**
> *Turn 20: "Refocusing on Phase 2: API endpoints per project plan. Frontend is Phase 3."*
> *Turn 22: "API endpoint for /kpi-scores implemented. Ready to move to the next endpoint."*

---

## 4. Skill-Driven Workflow

### Problem: Security Afterthought

Developer asks Claude to add a new API endpoint. Claude writes the code, opens a PR. Two days later, a security review catches SQL injection in a query parameter.

### Fix: Mandatory Skill Gate

```markdown
| Task type              | Skill             | Required? |
|------------------------|-------------------|-----------|
| Pre-PR security review | `/security-audit` | MANDATORY |
| API endpoint code      | `/api-security-best-practices` | MANDATORY |
```

Now Claude's flow is:
1. See task: "add API endpoint"
2. Check trigger table → matches "API endpoint code"
3. Invoke `/api-security-best-practices` BEFORE writing code
4. Write endpoint with parameterized queries, input validation, rate limiting
5. Before PR: invoke `/security-audit`
6. Security audit passes → open PR

The SQL injection never exists because the security skill was loaded before the first line of code.

---

## 5. Ground Truth Verification

### Problem: Confident Hallucination

```
User: "How many users do we have?"
Claude: "Based on the schema docs, the users table should have
        approximately 50,000 rows from the last import."
```

The docs are from 3 months ago. The actual count is 12,847 because the import was filtered.

### Fix: Verify Before Claiming

```
User: "How many users do we have?"
Claude: *runs SELECT COUNT(*) FROM users*
Claude: "12,847 rows in the users table."
```

No hedging, no "should have", no "approximately". Run the query. State the fact.

**Verification checklist:**

| Instead of...                    | Do this...                           |
|----------------------------------|--------------------------------------|
| "The table has ~50K rows"        | `SELECT COUNT(*) FROM table`         |
| "The function is in utils.py"    | `grep -r "def function_name" .`      |
| "The API returns JSON"           | `curl -s endpoint \| head`           |
| "The migration was applied"      | `\d table_name` in the database      |
| "The config has X setting"       | `cat config.yaml \| grep setting`    |

---

## Anti-Patterns to Avoid

### The Kitchen Sink CLAUDE.md
Stuffing 500 lines of rules into one file. Claude can't prioritize, so it follows whichever rules are closest to the bottom of the context window.

### The Wishful Handoff
"Worked on stuff. Continue from where I left off." Next session has no idea what "stuff" means.

### The Honor System
"Please follow security best practices." Without a mandatory skill gate, this is ignored under time pressure.

### The Static Plan
Writing a project plan once and never updating it. By turn 30, Claude is working from an outdated plan and making wrong decisions.

### The Documentation Lie
"As documented in our API spec..." — documentation is a snapshot of intent, not a source of truth. The database is the source of truth. The running code is the source of truth.

---

## 6. The Rationalization Detector

### Problem: "Valid Drift" That's Actually a Gap

After a multi-PR sweep where Claude touched 12 sibling surfaces, you ask it to debrief. Claude files three items as *"valid drift but distinct from the plan"* — framed as accepted, documented divergence.

You read the list and your gut says: *some of these sound like real problems, not drift.*

### Fix: Two Tests Before Filing as Drift

Before placing an item in a "valid drift" / "documented divergence" / "defensible design choice" bucket, run two tests:

1. **Does it violate a written ADR?** If yes, it's a gap. The ADR existed to record the architectural commitment; ignoring it without an updating ADR explaining the new policy is silent violation.
2. **Is it the lone exception to a sweep that touched every sibling?** If yes, it's a gap. The bar is *"explain the exception or fix it,"* not *"document the divergence."*

### Real Example

A platform-wide scope split moved every mutation surface from `read:*` to `write:*`:
- `workspaces` POST/PATCH/DELETE/restore → `write:workspaces` ✓
- `lineage_comments` POST/DELETE → `write:workspaces` ✓
- `notifications` PATCH → `write:workspaces` ✓
- `audit_exports` POST → **still `read:audit`** ← lone exception

The lone-exception code rationalized itself in its docstring: *"an export is just a list delivered as a file."*

True of the data shape. False of the side effects: POST inserts a row, consumes CPU + disk, issues a 5-minute signed-URL capability. That's unambiguously a write. The "fancy read" framing rationalized the inconsistency.

**Score from one real session:** Claude filed 5 items as "valid drift." Two tests applied → 3 of 5 were rationalizations.

### Pattern

When Claude (or a teammate, or you) reaches for *"valid drift"* / *"acceptable divergence"* / *"defensible design choice"* — pause and apply the two tests. If either fires, promote to a Known Gap with concrete action items.

---

## 7. Bot Reviews Need Verification, Not Obedience

### Problem: Confident-Sounding Wrong Suggestion

Bot review on a PR flags a `move_to_end(key)` call after an `OrderedDict[key] = value` assignment as redundant. The bot's reasoning: *"OrderedDict.__setitem__ appends new keys to the tail on assignment."*

You apply the fix. Tests pass. PR merges.

A week later, an LRU eviction bug surfaces: the cache promotes brand-new keys correctly but never re-promotes expired-but-still-cached entries when they're refreshed.

### Fix: Verify Semantic Claims Against Spec

The bot's claim was half-true: `__setitem__` appends NEW keys to the tail; it does **NOT** reorder EXISTING keys. The branch the bot didn't reason about — refreshing an entry that's still in the dict — is exactly the LRU-eviction failure mode `move_to_end` was protecting.

Trivial mechanical bot suggestions are fine to apply as-is (typos, missing imports, `encodeURIComponent` on a URL segment). **Semantic** bot suggestions — *"X is a no-op," "this branch is dead code," "this invariant holds"* — need a 60-second verification against the language spec or a microtest before applying.

### Heuristic

The phrase *"X always does Y"* in a bot review is the verification trigger. Always-claims about runtime semantics of standard-library data structures, async dispatch, lock ordering, iteration order, encoding boundaries — verify against docs.

---

## 8. Documentation Cadence (or: Why Plans Rot in 9 Days)

### Problem: Doc Drift That Becomes Doc Lies

Across a single sweep (15+ PRs over 9 days), the project plan and README go untouched. New routers ship, new auth surfaces ship, new scope vocabularies ship, new infra modules ship. The plan still describes the pre-sweep state.

By PR 16, the plan says *"BFF has 6 view-model endpoints"* but the router has 7. *"~124 pytest tests"* but the actual count is 221. *"Test counts unchanged"* but the suite grew by 100+ cases. A link points at `IMPLEMENTATION_GAP_ANALYSIS_2025_11_07.md` — a file that was deleted months ago and replaced by an in-plan section nobody wrote.

Future-Claude on continuation reads these counts as ground truth. Decisions get made on them. They were wrong.

### Fix: Cadence Trigger

Make doc-sync a standing rule, not a virtue:

```markdown
## Documentation Cadence (MANDATORY)

After every 5 merged PRs (or at any session-end checkpoint),
analyze whether the project plan and/or README need an update.

1. Read the plan's `Last Updated:` date.
2. List capability-surface deltas since that date:
   git log --since=<date> --oneline main
3. For each delta, check:
   - Plan's Phase status table reflects it?
   - README architecture bullets list it?
   - Any new gaps created (deploy never run, scope vocab needs
     reissue, test masks a pre-existing failure)?
4. Any "no" → open a `docs/<short-description>` PR.

Doc PRs are a legitimate output of the autonomous loop, not a chore.
```

### Why This Works

The audit IS the work. Running `git log --since=<plan_last_updated>` against the plan's status table makes the deltas obvious. The plan's `Last Updated` field becomes the audit anchor. A 5-PR cadence is short enough to catch drift while it's still cheap (3-line patch), long enough to avoid noise (no PR opens just to bump a date).

### Pairing With Tools

The `improve-codebase-architecture` skill works as a doc-vs-repo audit pass even though that's not its primary frame — give it the docs + ask it to verify claims against repo reality. It surfaces inflated/deflated counts, dead links, and silently-violated written commitments.

---

## 9. FastAPI Dependency Override Request-Injection Footgun

### Problem: A 422 Where You Expected an Override

You write a pytest fixture that overrides a FastAPI dependency. The fixture stashes some state on `request.state` and returns an actor string:

```python
def _override_helper():
    from fastapi import Request as _Request   # ← function-local + alias

    async def _gate(request: _Request) -> str:
        request.state.actor = "test-user"
        request.state.scopes = ["read:x"]
        return "test-user"

    app.dependency_overrides[require_api_key] = _gate
```

Every test using this override returns HTTP 422:

```json
{"detail":[{"type":"missing","loc":["query","request"],"msg":"Field required"}]}
```

FastAPI saw `request` and routed it as a query parameter instead of injecting the Starlette `Request`. You lose 30 minutes wondering why.

### Fix: Module-Scope Canonical Import

FastAPI re-introspects the override's signature **by name**, not just runtime type identity. An aliased or function-local `Request` import passes `isinstance(x, Request)` but fails the name-based signature matcher.

```python
# Module scope, canonical name
from fastapi import Request

def _override_helper():
    async def _gate(req: Request) -> str:   # ← injects correctly
        req.state.actor = "test-user"
        req.state.scopes = ["read:x"]
        return "test-user"

    app.dependency_overrides[require_api_key] = _gate
```

### Pattern

Move dependency-override signatures' type annotations to module-scope canonical imports. Document the footgun in the shared fixture's docstring so the next teammate doesn't pay the 30-minute tax. The pattern generalizes: any framework that does signature introspection on overrides (Pydantic v2, FastAPI, several DI containers) can fall to the aliased-import trap.
