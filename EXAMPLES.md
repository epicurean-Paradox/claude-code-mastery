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

---

## 10. The Test-Suite Inclusion Gate

### Problem: Production-Grade by Addition

A long autonomous sweep produces an obvious-feeling impulse: "add more tests." Coverage thresholds, mutation testing, contract fuzzing, visual regression, load testing, a11y, Storybook, MSW — every one is *good practice in the abstract*. So they get added. Six months later half the suites are skipped or stale, CI is 18 minutes, and the maintenance attention is leaking out of the actual product work.

The failure mode is real and asymmetric: a missing test surfaces once (and gets noticed); an unjustified test runs every CI minute forever (and never gets removed).

Worked instance from one 14-PR sweep:
- Built a manual formulas editor PR (#137). Had to delete a render-time test because the project never bundled a DOM-rendering library. Concrete gap, real cost.
- Considered adding `@testing-library`, `coverage-v8`, `schemathesis`, Storybook, Stryker (mutation testing), k6 (load testing), MSW, vitest-axe, visual regression. Eight candidates, all reasonable.
- Adding all eight would have doubled CI time + tripled the maintenance surface for the next eight PRs.

A gate was needed that wasn't "is this best practice?" (the answer is always yes) but "is this best practice **for this codebase, this week**?"

### Fix: Five-Test Gate, Default DEFER

Run every candidate test suite, testing-tool dependency, or coverage system through five tests. INCLUDE only if **all five pass**. Otherwise DEFER and write the trigger condition that flips the failing test.

| # | Test | Question | Defer trigger when this fails |
|---|---|---|---|
| 1 | Concrete-gap | Can I name a recent PR or shipped bug where the absence of this tool bit us? | "best practice but no recent bite" |
| 2 | Consumer | Does a workflow, CI gate, or human reviewer actually consume this signal today? | "we'd read the coverage report... someday" |
| 3 | Substitution | Is the signal already arriving from another mechanism (bot reviewer, type checker, existing test, CI step)? | "duplicative until substitute fails" |
| 4 | Prerequisite | Is the surface the tool measures actually present in the system today (deployed env, rendered component, populated DB)? | "load-testing nothing-in-prod is theater" |
| 5 | Volume | Does callsite / scenario count cross the abstraction-overhead-vs-ad-hoc-cost threshold? | "MSW for 1 callsite" |

### Worked Decisions From the Sweep

The same five tests, applied uniformly, produced these decisions in a single autonomous loop:

| Candidate | Tests | Verdict | Why |
|---|---|---|---|
| `@testing-library/react` + `user-event` + `jest-dom` | 1 ✅ 2 ✅ 3 ✅ 4 ✅ 5 ✅ | INCLUDE | Test 1 fired on PR #137 — had to delete a render-time test the day before. |
| `@vitest/coverage-v8` | 1 ✅ 2 ✅ 3 ✅ 4 ✅ 5 ✅ | INCLUDE | Backend already runs `--cov-fail-under=80`; frontend had zero signal. Test 1 = pass via asymmetry. |
| `schemathesis` (OpenAPI fuzz) | 1 ✅ 2 ✅ 3 ✅ 4 ✅ 5 ✅ | INCLUDE | First sweep flagged ~50 latent shape-drift bugs → unguarded surface was real. Default-skipped behind `RUN_CONTRACT_TESTS=1` until retrofit lands. |
| `vitest-axe` (a11y) | 1 ✅ 2 ✅ 3 ✅ 4 ✅ 5 ✅ | INCLUDE NEXT | a11y bugs surface in real review; setup is cheap. |
| Storybook | 1 ❌ 2 ❌ | DEFER | No designer-engineer review workflow exists. **Trigger**: designer asks to review components without a running app, OR component count > 150. |
| Stryker (mutation testing) | 3 ❌ | DEFER | Bot reviewers already catch weak assertions. **Trigger**: bot reviewers go away OR test-quality bugs accumulate. |
| k6 (load testing) | 4 ❌ | DEFER | No prod deployment to load-test. **Trigger**: first `terraform apply` smoke through ALB lands. |
| MSW (Mock Service Worker) | 5 ❌ | DEFER | 1 callsite uses ad-hoc fetch mocking. **Trigger**: render-time API tests cross ~5 files OR ad-hoc pattern breaks on concurrent / streaming fetches. |

### Why This Works

The gate doesn't depend on memory or taste. Each test has an unambiguous answer pulled from the same artefacts that drive every other engineering decision: recent PRs (Test 1), the actual CI config + reviewer roster (Tests 2 + 3), the deployment state (Test 4), and a `grep -c` on the codebase (Test 5).

A candidate that fails any test still gets a *Known Gap entry naming the failing test and its precondition*. So the gate isn't "reject and forget" — it's "defer with a named trigger condition." The next sweep cycle re-evaluates: did the prerequisite land? did the substitute fail? did the callsite count cross the threshold? When a trigger fires, the candidate auto-promotes to INCLUDE without a fresh debate.

The behavioural shift: the impulse "add more tests" gets cashed out as a 5-line table, not a vibe. The same five tests, written into CLAUDE.md, also resist personality drift across sessions — the next context window applies the same gate, not whatever the current session's enthusiasm dictates.

### Pairing With Other Patterns

- **Pattern 6 (Rationalization Detector)** applies to the gate's own decisions: if a candidate fails Test 4 but the response is "well, surely we'll deploy eventually," that's a rationalization, not a trigger.
- **Pattern 8 (Documentation Cadence)** is what catches a stale trigger. The 5-PR doc audit asks: did any deferred candidate's precondition just land? If so, promote it.
- **Pattern 7 (Bot Verification)** applies to the gate itself when a reviewer suggests "add Storybook" or "use MSW." The semantic claim "this codebase needs X" demands the same five tests — not deference to the suggestion.

---

## 11. Delegation Poker for AI Loops

### Problem: Autopilot by Default

The default working assumption of most AI coding agents (the human's, and often the agent's own) is *"I delegate; you execute."* This works for bounded tasks — typo fixes, single-function rewrites, mechanical renames. It fails for anything where judgment is load-bearing: scope-shift decisions, deploy-vs-ship choices, weighing two non-obvious options against each other.

A real session: after 14 merged PRs, the operator asked *"why have you been moving the deploy steps ahead instead of solving them?"* The agent had been operating as if the standing instruction was "ship the next reviewable artifact" — when the actual instruction surface was much more nuanced. The operator's response named the gap directly:

> *"In Management 2.0 delegation poker, I don't fully delegate on you for everything. I delegate, Inquire, advise you, look for agreement, expect you to consult me, or I'll tell you what to do, regarding the circumstances and according to the context."*

The agent was at delegation level 7 ("Delegate") when most of the work was actually at level 3-5 ("Consult / Agree / Advise"). Cost: 14 PRs of merged-without-deploy work, plus the architectural drift that came with it.

### Fix: Codify Delegation Level at Task Entry

The seven levels from Management 3.0's *Delegation Poker* map cleanly onto AI work:

| Level | Name | What the AI does | Example |
|---|---|---|---|
| 1 | Tell | Operator decides; AI executes the literal instruction | "Rename foo to bar in api/auth.py" |
| 2 | Sell | Operator decides; AI follows + explains the trade-offs to peers | "Apply this migration; explain to the team why we chose schema X" |
| 3 | Consult | Operator decides after asking AI's input | "What's wrong with the dashboard? I'll choose the fix" |
| 4 | Agree | AI + operator decide together | "Should this PR ship now or wait for staging?" |
| 5 | Advise | AI decides after asking operator's input | "Draft the deploy plan; I'll review the major calls" |
| 6 | Inquire | AI decides; informs operator after | "Address all bot findings + reply; tell me if anything fails CI" |
| 7 | Delegate | AI decides; no inform needed for routine outcomes | "Fix typos in the docs" |

The default-level trap: an operator says *"run the autonomous PR loop"* and the AI silently snaps to Level 7. The phrase *"autonomous"* meant "self-pace the cycle"; it did NOT mean "make scope, architecture, and prioritization calls without consulting."

### Codification Recipe

Add to every project's `CLAUDE.md`:

```markdown
## Delegation Level

For each substantive task, state the delegation level (1-7) you are operating
at, in the first response of that task. Default to **Consult (3)** when
unclear. Re-confirm whenever directives shift.

The default is NOT "Delegate." A multi-PR sweep, an architecture change, a
deploy, a non-trivial refactor — these are 3-5 by default unless the operator
explicitly upgrades.
```

### The "Stale Schedule" Anti-Pattern

A specific failure mode worth naming separately: the agent schedules a wake-up (cron, `ScheduleWakeup`, `/loop`) with a prompt that captures the task as it was understood at scheduling time. The operator then changes direction. The wake-up fires later carrying the *stale* prompt, and the agent — without surfacing the conflict — executes it.

In the session this pattern was extracted from: the `/loop` task was scheduled with "merge in-flight PRs + start vitest-axe." Twenty minutes later the operator chose Option 1 ("close those PRs, deploy first"). The wake-up fired ten minutes after that, carrying the stale prompt. The right move was to *pause*, surface the conflict between the scheduled prompt and the most-recent directive, and ask which read of the operator's intent governs. The wrong move (the autopilot move) would have been to execute the stale prompt and silently undo Option 1.

Codify:

```markdown
## Schedule vs Directive Conflict

When a scheduled task (cron / wake-up / loop fire) carries a prompt that
pre-dates the operator's most-recent directive, treat the directive as
authoritative. Do NOT execute the scheduled prompt. Surface the conflict,
name both reads, and ask which governs.
```

### Why This Works

The delegation level is a one-line negotiation that takes ten seconds at task start and prevents hours of misaligned work. It's also one of the few rules that an AI *can't* drift away from in long sessions: each task forces a fresh re-declaration, so personality decay doesn't quietly raise the level.

### Pairing With Other Patterns

- **Pattern 3 (Session Decay)** prevents level-drift inside a single task (re-read every 10 turns). Pattern 11 prevents level-drift *across* tasks.
- **Pattern 6 (Rationalization Detector)** applies to the level itself: if you find yourself filing decisions as "I'm operating at Delegate" without an explicit upgrade from the operator, that's a rationalization.

---

## 12. The Build/Ship Gravity Trap

### Problem: Code Work Eats Deploy Work

Over a 14-PR sweep, every PR shipped meaningful code: a new test stack, a contract-fuzz harness, a frontend route, a security tightening. CI green, bot reviews passed, merges flowed. After 14 merges, the operator asked the question that exposed the gap:

> *"What's missing to see, in production, the real functioning platform instead of what we see today?"*

Answer: **everything operational.** Zero AWS resources provisioned. Zero data in any cloud DB. Zero verification that the platform worked end-to-end outside a laptop. The codebase had advanced by 14 PRs; the deployed surface had advanced by zero.

The autonomous loop wasn't lazy or wrong. It was working a gradient — *the gradient of "which task produces the fastest reviewable, mergeable artifact?"* — and that gradient pointed at code work, never at deploy work, every single iteration.

### The Eight Biases

| # | Bias | Effect |
|---|---|---|
| 1 | Iteration speed | Code edit → test → commit: ~30s. `terraform apply` → debug → re-apply: ~25 min. Loop optimizes for short cycles. |
| 2 | Reviewable artifacts | A PR has a diff, bot reviews, green checks, a merge counter. A deploy returns a URL — no PR surface, no merge increment. |
| 3 | Risk asymmetry | Code mistake: `git revert`. Terraform mistake: real $$$ AWS bill, half-created infra, security-group misconfig. Loop chooses safety. |
| 4 | Access friction | Code is local. Terraform needs real AWS creds, Bedrock model access, possibly budget approval. Friction the loop can't resolve alone. |
| 5 | "Code complete = done" trap | Plan tracks Phase G as `CODE COMPLETE \| 100%`. The "deploy: unverified" asterisk reads as a footnote, not a blocker. |
| 6 | No CI alarm | Missing pytest → red CI. Un-applied terraform → silence. Nothing in the workflow surfaces deploy debt. |
| 7 | Role assumption | Deploys traditionally owned by "DevOps." Loop instincts ship code, not infra. |
| 8 | No named trigger | The plan was honest about the gap (Gap #1 = HIGH). But no entry said *"STOP coding now, deploy first."* So every cycle pulled the next reviewable code task off the queue. |

Items 1, 2, and 6 dominate. The reward function is "produce a reviewable, mergeable artifact." Deploy produces no PR-shaped output until it succeeds — and one URL when it does. The cost function rewards 14 small PRs over 1 deploy.

### Fix: Install a CI Gate That Blocks Surface-Changing Work Until the Deploy Receipt Lands

The gate is mechanical, not aspirational. A repository variable (or a receipt file under `infra/`) flips from `false` to `true` the moment the first successful `terraform apply` + smoke-test combination lands. A `deploy-gate.yml` workflow blocks `feat/*` PRs from merging while the variable is `false`. `chore/`, `fix/`, `docs/`, `test/`, and `refactor/` flow through unchanged — they don't grow user-facing surface.

```yaml
# .github/workflows/deploy-gate.yml
name: deploy-gate
on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened, labeled, unlabeled]
jobs:
  require-deploy-bootstrap:
    if: startsWith(github.event.pull_request.head.ref, 'feat/')
    runs-on: ubuntu-latest
    steps:
      - name: Check bypass label
        id: bypass
        run: |
          labels="${{ join(github.event.pull_request.labels.*.name, ',') }}"
          if [[ ",$labels," == *",bypass-deploy-gate,"* ]]; then
            echo "bypass=true" >> "$GITHUB_OUTPUT"
          fi
      - name: Require AWS_INFRA_BOOTSTRAPPED for feat/* PRs
        if: steps.bypass.outputs.bypass != 'true'
        run: |
          if [ "${{ vars.AWS_INFRA_BOOTSTRAPPED }}" != "true" ]; then
            echo "::error::feat/* PRs blocked until first terraform apply lands."
            echo "::error::Set repo var AWS_INFRA_BOOTSTRAPPED=true after deploy succeeds."
            exit 1
          fi
```

The bypass label exists for the one PR that IS the bootstrap enabler.

### Why "feat/* only"?

`chore/`, `fix/`, `docs/`, `test/`, `refactor/` ship value WITHOUT growing user-facing surface. Holding them hostage to deploy makes the working tree diverge from main while adding nothing to ship — the exact thing this gate exists to prevent.

`feat/*` is the prefix the team uses for surface-changing work. Accumulating `feat/*` on main without deploy = the exact failure mode this pattern addresses.

### Generalisation Beyond IaC

The build/ship gravity trap shows up anywhere "build" and "ship" are decoupled and the build side is the one with the reviewable artifact:
- Library code merges to `main`; releases never cut → install a `release-gate.yml` on commits with `BREAKING:`
- Test infra lands but never runs in CI → install a `coverage-gate.yml` requiring the new suite to be in CI before related PRs merge
- Migration files merged but never applied to staging → require a staging-applied receipt before merge

Same shape: gradient + gate.

### Pairing With Other Patterns

- **Pattern 8 (Documentation Cadence)** is the symptom-side detector — the 5-PR audit catches plan / runtime drift. Pattern 12 is the structural fix.
- **Pattern 11 (Delegation Poker)** is the meta-layer: even with the gate installed, the operator decides when to *upgrade* the level so the AI can run the deploy itself.
- **External precedent**: OpenAI's open-source Symphony orchestrator (github.com/openai/symphony) ships the same shape at product scale — always-on agents driven from an issue tracker with a mandatory human-review gate before anything lands.

---

## 13. Observability Before Autonomy

### Problem: The Loop Can't See What It Shipped

Once code leaves the repo, the autonomous loop is blind. A user asks *"what's wrong with the dashboard right now?"* and the AI has no path to answer that question without the operator pasting `aws logs tail` output into the prompt. The asymmetry is structural: the AI can write infrastructure-as-code but can't query the infrastructure-as-running-system.

This means the loop ships work it can't verify, can't diagnose, and can't fix from the same surface it used to write it. Every operational issue becomes a manual handoff — the exact thing the autonomy was meant to remove.

The traditional response is "add CloudWatch / Prometheus / Datadog." That layer captures *signals*. It does not capture *agency*. CloudWatch sees the error. The loop still can't read it.

### Fix: Build the Inspection Harness at the Same Time as the IaC

If you intend to operate via the repo (declare changes in code, redeploy from CI), the runtime needs to expose itself to the repo. Concretely, this is seven components — design them as a Phase, not as one-off scripts:

| # | Component | What it does |
|---|---|---|
| H1 | `inspect.yml` workflow | Manual-dispatch CI job. Pulls last 200 error lines from CloudWatch Logs Insights, current ECS service state, alarm states, RDS connection count. Posts to workflow log + optional PR comment. |
| H2 | `drift-detect.yml` workflow | Scheduled `terraform plan` against dev + staging. If the diff is non-empty, opens a GitHub Issue with the offending resources. |
| H3 | `smoke.yml` workflow | Every 15 min curl `/health` + `/v1/views/dashboard` with a service-key auth header. Pages on red. |
| H4 | `rollback.yml` workflow | Manual-dispatch. `aws ecs update-service --force-new-deployment --task-definition <arn>` for a chosen prior revision. One button. |
| H5 | MCP runtime-query tool | A server-side AWS-CLI wrapper exposing log queries to chat. Read-only. Per-tool RBAC (admin scope). |
| H6 | `/admin/runtime-status` API endpoint | Admin-scoped endpoint returning aggregated health (ECS / RDS / external-source reachability / Bedrock reachability) as JSON. |
| H7 | GitHub Actions → AWS OIDC | No long-lived keys in the repo. IAM trust via OIDC, scoped per workflow (inspect = read-only role; deploy / rollback = read-write role). |

H1 + H7 are the unlock — once those exist, an AI working from the repo can answer "what's broken right now?" without a manual `aws-cli` paste, and the answer is gated by IAM, not by trust.

### The "Build = Done" Failure Mode This Closes

A plan that lists CloudWatch + alarms as "monitoring done" misses the agency layer. The agent can't actually USE CloudWatch from the prompt surface — it has no shell-pipe into AWS. The Phase H components turn that signal layer into a *queryable surface from the same repo that wrote the IaC.*

```
       Without Phase H              With Phase H
       ─────────────────            ─────────────────
       User: "what's broken?"       User: "what's broken?"
       AI:   "I don't know.         AI:   *runs inspect.yml*
              Run aws logs tail            *reads CloudWatch
              and paste the output."        Logs Insights output*
       User: *runs cli, pastes*    AI:   "RDS conn pool exhausted
       AI:   "Looks like ..."             at 18:47; ECS task 3
                                          OOM'd. Here's the PR:"
                                          → opens PR with the fix.
                                          → deploys via gh workflow.
                                          → smoke confirms green.
```

### Why "Before Autonomy"

If you build the inspection harness *after* you build the autonomy, you accumulate technical debt in the operational surface that the autonomy then has to navigate around. The autonomous loop will pick the easiest task off the queue at every turn — and that task will never be "build the missing observability tool" because it doesn't produce a reviewable, mergeable artifact (Pattern 12 again). Observability *deferred* is observability *never built*.

The trigger: any time you write *"the AI will run this autonomously,"* you have already implicitly committed to building the inspection harness that lets the AI see what it's running. Doing one without the other is shipping a one-way street.

### Pairing With Other Patterns

- **Pattern 12 (Build/Ship Gravity Trap)** is what blocks code work until deploy lands. Pattern 13 is what makes the deployed state inspectable from the same code surface. They compose.
- **Pattern 11 (Delegation Poker)** is the operator's lever once the inspection harness exists: the operator can safely raise the delegation level on operational tasks because the AI now has the agency to actually act on what it observes.

---

## 14. Auth Surface Separation

### Problem: Same Vendor, Two Tokens, One Confusion

A real session: CI's auto-review job failed with *"ANTHROPIC_API_KEY: empty."* The product runtime uses AWS Bedrock to call Claude — no Anthropic key needed anywhere in the deployed stack. So why does CI need an Anthropic API key at all?

The intuition that *"if the product uses Bedrock, the whole stack uses Bedrock"* is wrong but extremely natural. It costs hours of misdirected debugging.

### Fix: Name the Two Surfaces Explicitly

When the same vendor (Anthropic, OpenAI, AWS, Google, etc.) provides both a **product API** and a **CI / dev tool**, the auth paths are almost always independent. Codify the separation in the project's CLAUDE.md so it's not rediscovered every time:

| Surface | Where it lives | Auth path |
|---|---|---|
| Product runtime | The deployed app (e.g. ECS, Lambda, Vercel) | Cloud-native IAM (e.g. AWS Bedrock IAM grant), no API key in source/secrets |
| CI / dev tooling | GitHub Actions runners, dev laptops | Vendor's hosted-action token (e.g. `claude_code_oauth_token`, OpenAI dev key) stored as a CI secret |

These pass through different network paths (your AWS account → Bedrock vs runner → `api.anthropic.com`), bill against different cost centres (your AWS bill vs your Anthropic subscription), and authenticate with different artefacts. Conflating them = a hot debug.

### Concrete Examples

| Vendor | Product surface | CI/dev surface | Common confusion |
|---|---|---|---|
| Anthropic | Claude via AWS Bedrock | `anthropics/claude-code-action` GitHub Action (OAuth or API key) | "We migrated to Bedrock; why does CI still need a key?" |
| OpenAI | Azure OpenAI Service deployments | OpenAI CLI / `openai` package on a laptop | "We're Azure-only; why does the dev container have an OpenAI key?" |
| AWS | Production workload | Local `aws-cli` for dev | "I gave the ECS task IAM; why does my terminal still need access keys?" |
| Google | Cloud Run service | `gcloud` CLI | "Service account exists; why does the developer still need OAuth tokens?" |

### Codification Recipe

Add to project CLAUDE.md:

```markdown
## Auth Surface Separation

This project has two distinct auth surfaces for vendor X:

1. **Product runtime** uses <cloud-native IAM path>. NO API key in
   `.env`, source, or secrets manager. The IAM grant is at <module>.

2. **CI / dev tooling** uses <vendor's tool-specific token>. Stored
   in <secret name> at <secret location>. Different cost centre,
   different audit trail.

When debugging an auth failure, identify which surface first. Failure
in CI = check the CI secret. Failure in production = check the IAM
grant.
```

### Why This Works

Naming the separation up front turns a multi-hour debugging session into a one-minute check: which surface is failing? The fix is in different places per surface. Without the naming, the natural assumption (one vendor = one auth path) sends you to the wrong file.

This pattern also catches the inverse mistake: an engineer fixing a "missing API key" issue in production by adding `ANTHROPIC_API_KEY` to Secrets Manager — when the actual fix is to grant Bedrock IAM permission to the ECS task role. The wrong fix would have shipped a secret the runtime never reads + left the real grant gap unaddressed.

### Pairing With Other Patterns

- **Pattern 7 (Bot Verification)** — when a bot says *"add the API key,"* verify *which* surface it's flagging. The right fix may be on the other side.
- **Pattern 13 (Observability Before Autonomy)** — your inspection harness should surface both auth paths separately. `inspect.yml` querying CloudWatch alarms shows runtime auth failures; `gh secret list` shows CI-tool token health. Different shells, same dashboard.

---

## 15. Verify Every Gate (Badge != Outcome)

### Problem: A Green Pipeline That Shipped Nothing

A deploy phase strung together gates: push -> remote -> merge -> deploy -> render -> wire -> serve. Each green signal was read as proof of the next state. Result, in turn: a branch that never reached the remote (clean `push` exit, `-u` no-op'd), a PR MERGED green with the *pre-fix* code on `main`, a merge that never triggered a deploy, a deploy whose buttons rendered as empty boxes, an endpoint no frontend called, and an integration "live" on a `401` that returned `502` to authed traffic.

### Fix: One Probe Per Transition

Never infer a downstream state from an upstream signal. Each "therefore" gets a cheap, specific check:

```bash
# "Pushed" -> confirm the remote actually has your SHA
git push origin HEAD:my-branch
git ls-remote origin my-branch          # SHA must equal local HEAD; clean exit is not enough
gh pr view --json headRefOid --jq .headRefOid

# "My fix is in main" -> confirm by content, not by the MERGED badge
git show origin/main:path/to/file.py | grep 'the_fix_token'

# "Merged -> deployed" -> confirm a deploy run was actually created
gh run list --workflow deploy.yml --event workflow_run --limit 3

# "Deployed -> working" -> observe the live surface, don't trust the build
curl -sS https://app.example.com/health
# and for UI: load it (Playwright / real browser); a correct build can render dead DOM

# "Endpoint exists -> feature done" -> wiring is a separate axis
rg "fetch\\(['\"].*/v1/the-endpoint" frontend/src   # does anything actually call it?

# "401 on no-auth -> live" -> the data path is the real gate
curl -sS -H "Authorization: Bearer $TOK" https://app.example.com/v1/data   # expect 200 + payload shape
```

**The rule**: a chain is only as real as its least-verified link. The badge reports a step was *attempted*; only a probe confirms the *downstream state*. (See LESSONS Lesson 11.)

---

## 16. Diagnose at the Layer That Actually Failed

### Problem: Right Symptom, Wrong Layer

A binary upload returned `403`. The frontend showed "permission denied," and a full session went into app/auth code. The real rejecter was a WAF body-size rule returning an nginx HTML page; the app logged zero requests. Same family, other sessions: a model swap threw on every call (the new family rejected a `temperature` param the old one accepted -- an *access* check had passed, a *request-compatibility* check had never run); a deploy kept targeting the old account because an *environment-scoped* CD variable silently overrode the *repo-scoped* one; a visual-regression harness kept "passing" stale output because a build mode was incompatible with the harness server and reused a cached prerender.

### Fix: Identify the Rejecting Layer by Its Signature Before Theorising

```
403 with an HTML error page + app logged nothing  -> gateway / WAF / proxy, not the app
403 with app JSON                                 -> the app's authz
Throws right after a model/provider swap          -> request-param compatibility, not access
                                                     (run ONE real end-to-end call after any swap)
Deploy targets the wrong place despite a repo var -> an environment-scoped var of the same name
                                                     overrides it; update + verify which one is read
Harness shows stale output after a confirmed change-> build-mode / cache mismatch, not the change;
                                                     force a faithful regen before trusting pass/fail
```

Map distinct upstream rejections to distinct user-facing messages instead of collapsing every `403`/failure to "permission denied." Naming the layer turns a multi-hour hunt into a one-minute check.

---

## 17. Driving PRs Through a Bot-Reviewed, Protected main

### Problem: "Needs --admin" on an All-Green PR

CI is green, but `gh pr merge` refuses and asks for `--admin`. The instinct is "a check is missing." It usually isn't -- it's the conversation-resolution gate: the protected branch requires every review thread *resolved*, and bot reviewers leave threads, not approvals.

### Fix: Resolve Threads via GraphQL, Don't --admin Past Them

```bash
# Each addressed thread needs an explicit resolve. Loop per thread ID --
# concatenating IDs returns NOT_FOUND.
gh api graphql -f query='
{ repository(owner:"O",name:"R"){ pullRequest(number:N){
    reviewThreads(first:100){ nodes { id isResolved } } } } }' \
| jq -r '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved|not) | .id' \
| while read -r tid; do
    gh api graphql -f query='mutation($t:ID!){resolveReviewThread(input:{threadId:$t}){thread{isResolved}}}' -f t="$tid"
  done
gh pr merge N --squash --delete-branch     # now passes without --admin
```

### And: Bots COMMENT, They Don't APPROVE

A solo-author + bots topology never receives a human `APPROVED`. Treat **effective approval** = CI green AND no unresolved HIGH/sec-HIGH on the latest commit from any bot reviewer AND every bot thread resolved. Then rebase + merge autonomously -- but always `--force-with-lease` (never bare `--force` except on a provably solo-owned branch where lease rejects on a stale tracking ref), and still pause to ask on multi-author branches, non-trivial conflicts, or a non-`main` base.

When even the merge git-ops fail (a flaky SSH agent, a credential-helper timeout), merge through the API instead of the local checkout:

```bash
gh api -X PUT repos/O/R/pulls/N/merge -f merge_method=squash -f sha="$HEAD_SHA"
```

(Pairs with LESSONS Lesson 9 -- the PR, not the working tree, is the durable unit of state.)

---

## 18. The False-DONE the Test Defended

### Problem: A "DONE" Backed by a Test That Asserts the Bug

A plan row read: *FI-3 DONE -- conversation-first entry, NO prefilled dashboard; submitting a question sets the sentinel, then propose_workspace, then a human Create click, then the dashboard.* It cited an end-to-end test as proof.

The shipped code did the opposite. On submit, `page.tsx:234-240` set `activeWorkspaceId` to a truthy sentinel (`"unsaved"`); the render gate at `:277` checked `=== null`; `workspace-view.ts:16-23` floored the view at `'dashboard'`. So the live organisation dashboard rendered the instant a question was submitted -- before any proposal or Create click. The operator had flagged exactly this, three times across three weeks.

The decisive part: the cited test, `chat-entry.realdata.spec.ts:57-64`, **asserted the dashboard is visible right after submit**. It was green. It had been written from the observed behaviour, so it pinned the regression as the contract, and the green check propagated into the plan's DONE.

### Fix: Read the Assertion Against Intent, Not Against the Code

```bash
# Don't accept "the e2e is green" as "the increment is done."
# Open the test the claim rests on and compare its assertions to the SPEC.
rg -n "expect|toHaveText|toBeVisible" frontend/e2e/realdata/chat-entry.realdata.spec.ts
# Ask: does this assert the INTENDED behaviour, or the SHIPPED behaviour?
# If it mirrors shipped output, a passing run certifies the regression.
```

The remedy was structural: correct the plan row from DONE to PARTIAL with the file:line evidence, open a Gap for the entry regression, and rewrite the test to assert the intended flow (prompt/pending state on submit; dashboard only after a proposal+Create) so the suite would fail on the regression instead of defending it.

### Why It Was Invisible

The gate was green, so nothing drew attention to it. Green is the camouflage. The only thing that surfaces a test asserting the wrong behaviour is a human or agent reading the assertion against the spec -- which is why "has a passing test" and "does the intended thing" must be checked as two separate claims.

(Pairs with LESSONS Lesson 16 -- a green test can certify the wrong behaviour -- and Lesson 11 -- the badge is not the outcome.)

## 19. Subagent Model Routing: the Fan-Out Silently Bills at the Parent's Tier

### Problem: A Default Nobody Chose Decides the Spend

Claude Code resolves a subagent's model in this order (official docs, fetched 2026-07-05): (1) the `CLAUDE_CODE_SUBAGENT_MODEL` environment variable, (2) the per-invocation `model` parameter, (3) the subagent definition's `model` frontmatter, (4) the main conversation's model. The frontmatter field defaults to `inherit` -- "uses the same model as the main conversation." The Agent SDK mirrors it: AgentDefinition.model "Defaults to main model if omitted."

Consequence: run the main loop on a top-tier model and every subagent that no layer above (4) overrides runs on that same top-tier model. A review council of 8 agents is 8 top-tier context windows, not 1. Nothing in the transcript flags it -- the badge (subagent ran, returned a summary) looks identical at every tier. **Runtime-verified 2026-07-05**: an un-overridden general-purpose subagent spawned from a Fable 5 main session recorded `claude-fable-5` in its transcript JSONL -- the doc's claim, observed live (Lesson 11: the doc is the badge; the transcript's model field is the outcome).

Exceptions that keep "every subagent" from being literally true:
- Built-in Explore inherits but is capped at Opus on the Claude API; on any other provider (Bedrock, Vertex, Foundry) it inherits the main model directly -- the cap does NOT protect a Bedrock-billed stack (see Example 14 on which surface bills where).
- Some built-in helpers run fixed models (e.g. statusline-setup, claude-code-guide).
- An org `availableModels` allowlist can veto an explicit frontmatter/env value, and the subagent then falls back to the inherited model -- an override that silently un-overrides.

### The Fork You Can't Cheapen

Two spawn types answer the routing question oppositely (docs fetched 2026-07-05):

|                         | Fork                             | Named subagent                        |
| :---------------------- | :------------------------------- | :------------------------------------ |
| Context                 | Full conversation history        | Fresh context with the prompt passed  |
| System prompt and tools | Same as main session             | From the subagent's definition file   |
| Model                   | Same as main session             | From the subagent's `model` field     |
| Prompt cache            | Shared with main session         | Separate cache                        |

- No fork model override exists as of the doc snapshot: the documented fork parameter surface has no `model`, and typing `/model` in a fork's transcript view changes the MAIN conversation's model. "Cannot be routed" is an absence-of-mechanism claim anchored to 2026-07-05 -- re-verify against the CHANGELOG before relying on it.
- A fork is not simply the expensive option: its first request reuses the parent's prompt cache -- the docs call forking "cheaper than spawning a fresh subagent for tasks that need the same context." The real trade: fork = parent model + full conversation + cache-discounted input, for side tasks needing the whole situation and parent-grade judgment; named subagent = any model + fresh context + separate cache, for narrow tasks a cheaper tier can execute from a self-contained brief. Routing a context-heavy side task to a cheap named subagent forces you to re-explain everything the fork would have inherited -- sometimes costing more than the tier discount saves.

### The Naming Trap: a Skill's `context: fork` Is Not a Fork

The skills doc reuses the word for the opposite semantics. A skill with `context: fork` runs in an ISOLATED subagent -- no conversation history -- and its `agent:` field determines the execution environment (model, tools, permissions). Point `agent:` at a custom subagent whose definition sets `model: haiku` and the skill runs cheap. Same word, opposite answer on both axes. Any routing rule you write must name which "fork" it governs.

### Fix: Make the Model an Explicit Field, Not an Inherited Accident

The defect is not "expensive model" -- resources are neutral, and a judgment-heavy verify pass may need exactly the parent's tier. The defect is the tradeoff being decided silently by a default: the same failure shape as Lesson 15, where the human owns the cost/accuracy tradeoff and never gets to have it silently decided -- in either direction. Down-tiering a judgment-heavy checker to save tokens is the mirrored version of the same mistake.

Verified mechanics for the explicit field (docs + installed sdk-tools.d.ts, 2026-07-05): frontmatter `model:` accepts an alias (`haiku`, `sonnet`, `opus`, `fable`), a full model ID, or `inherit`; the Agent tool's per-invocation `model` param takes precedence over frontmatter; `effort:` overrides the session effort level per agent (docs list low/medium/high/xhigh/max; one probe of an installed binary's embedded schema omitted xhigh -- the enum is version- and model-bound, re-verify on the installed build before quoting it as exact).

Enforcement, because a lesson that is not a gate gets re-violated (Lesson 17):
1. Every custom subagent definition declares `model:` explicitly. `model: inherit` is legitimate -- but written down, so the choice is visible in review, not implied by omission.
2. Any fan-out (review council, sweep, Ultracode run) states agent count x model tier next to the coverage statement Lesson 7 already requires.
3. Route by AMBIGUITY, not task size: top tier for planning, architecture, judgment calls, final verification; mid tier for standard codegen and exploration; bottom tier only for lookup-shaped tasks. Exploration floor is the mid tier -- a confidently-wrong cheap summary the orchestrator trusts costs more than it saves.
4. Anything that must be cheap must not be a `fork`.
5. Non-Anthropic models are not a native alias. Some third-party providers publish Anthropic-compatible endpoints reachable via environment variables alone; others need an external CLI wired as a subprocess. Either way it is an integration decision, not a frontmatter value -- verify the specific provider's path before planning around it.

### Provenance

The mechanism is doc-verified and runtime-verified as noted above. The framing that surfaced it ("what Anthropic engineers use", specific price ratios) came from an X-research sweep whose own raw notes mark those UNVERIFIED -- the posts remain DATA; everything above cites the official docs, the installed schema, or a first-hand runtime probe. Cost-magnitude language is deliberately absent: no per-token price appears here because no pricing primary was fetched.

### Pairing With Other Patterns

- Lesson 7 -- agent count is one cost axis; per-agent model tier is the other.
- Lesson 11 -- the doc is the badge; the model ID recorded in the subagent's transcript JSONL is the outcome.
- Lesson 15 -- silent defaults must not decide the human's cost/accuracy tradeoff.
- Example 14 -- which auth/billing surface the subagent runs on decides whether the Opus cap even applies.

## 20. /goal Is the Native End-State Gate -- and "Achieved" Is Still a Badge

### Problem: Autonomy With No Machine-Checked Stop Condition

Example 12's build/ship trap and Lesson 17's re-violated lessons share a root cause: an autonomous loop whose "done" was decided by the same model doing the work. Until now this repo's fixes were externally wired -- CI receipt gates, Stop hooks, checklist lines. Claude Code ships a native mechanism: `/goal <condition>` (official docs at code.claude.com/docs/en/goal; present in the installed CLI, string-probed 2026-07-05: "/goal <condition> to set another", "/goal clear to stop early", "/goal is only available in trusted workspaces"). It sets a completion condition; after every turn a separate small fast model judges whether the condition holds, re-prompts Claude with the reason if not, and clears the goal when it does. `claude -p "/goal <condition>"` drives the loop to completion in a single invocation.

### Fix: Use /goal as the Gate, and Verify Its "Achieved" Like Any Other Badge

Two facts from the official docs decide how to use it safely:

1. **The evaluator does not call tools.** It judges ONLY what Claude has surfaced in the transcript. A condition that does not name its own ground-truth check is grading claims, not outcomes -- Lesson 11 applied at the goal layer.
2. **Completion is decided by a fresh model, not the one doing the work** -- structurally the right separation (checker != worker), but still a model reading a transcript, not a probe of live state.

So a condition needs all three of:

```text
# One measurable end state + a stated check + constraints that must hold
/goal all tests in test/auth pass -- prove it: `npm test` exits 0 in the transcript;
no file outside test/auth or src/auth is modified (`git status` shown clean of others);
or stop after 20 turns
```

And when the loop reports achieved, run the one downstream probe before reporting done (Example 15's table): the goal-achieved entry certifies the transcript convinced a small model, not that the remote has your SHA or the deploy ran.

Mechanism notes worth knowing before relying on it: `/goal` is a wrapper around a session-scoped prompt-based Stop hook, so it is unavailable when `disableAllHooks` or `allowManagedHooksOnly` is set (the installed CLI's own strings confirm: "/goal can't run while hooks are restricted"); one goal per session; a goal still active at session end is restored on `--resume`. [verified 2026-07-05, live cycle observed on CLI v2.1.198: a nested INTERACTIVE session driven over a PTY with expect (the earlier headless `claude -p '/goal ...'` hang was the nested-CLI footgun, not /goal). Observed first-hand in the captured transcript: the "Goal set: <condition>" acknowledgement; a "/goal active (10 ...)" status indicator carrying a turn budget; goal evaluation running among the session's stop hooks ("running stop hooks... 0/2"); the worker model Write-ing the goal's target file mid-turn; then "Goal achieved (10s / 1 turn / 691 tokens)" with the goal clearing -- and the ground truth on disk (the condition's file, byte-exact content). Still unobserved: the evaluator's re-prompt REASON text on an UNMET turn -- the condition was satisfied on the first turn, so that single sub-behavior stays doc-verified only. Reusable driving notes: ink's renderer interleaves cursor-move codes between words, so expect string-matching against the TUI is unreliable -- pace with fixed sleeps, send per-keystroke (send -s) plus Enter, and anchor success on files-on-disk, never UI strings; bracketed-pasting several messages in a row concatenated them into ONE composer submission (a paste/submit race) and poisoned the goal condition with the follow-up text -- one message per submit.]

**Cross-refs**: Lesson 17 -- a nameable native enforcement mechanism, removing one excuse for a lesson with no gate. Lesson 22 -- /goal's condition can carry the iteration cap ("or stop after N turns"). Example 12 -- a lighter-weight alternative to the CI receipt gate. Example 11 -- a goal set before a newer operator directive is a stale prompt; the directive governs. Lesson 11 -- the achieved badge gets its own probe.

**Provenance**: surfaced via a third-party "god mode" brief (untrusted DATA; its GitHub skill fails the skill-security gate and must not be installed -- see Lesson 21); every operational claim above is grounded on the official docs and the installed CLI only.

## 21. The Harness Is Half the Benchmark

### Problem: A Leaderboard Number Read as a Model Property

"Model M scores 65% on benchmark B" reads like a fact about M. It is not -- it is a fact about a system: model + harness + environment + feedback loop. arXiv:2606.17799 ("Position: Coding Benchmarks Are Misaligned with Agentic Software Engineering"; full text fetched and Table 1 re-verified 2026-07-05) extracts TerminalBench leaderboard entries for a single fixed model, Claude Opus 4.6, across 9 different agent harnesses on the same task distribution:

```
Agent           Org             Accuracy
ForgeCode       ForgeCode       79.8 +- 1.6   (paper-only; NOT on live tbench 2.0 as of 2026-07-05)
Capy            Capy            75.3 +- 2.4   <- live-verified top
Terminus-KIRA   KRAFTON AI      74.7 +- 2.6
TongAgents      Bigai           71.9 +- 2.7
Droid           Factory         69.9 +- 2.5
Crux            Roam            66.9 (N/A)
Mux             Coder           66.5 +- 2.5
Terminus 2      Terminal-Bench  62.9 +- 2.7
Claude Code     Anthropic       58.0 +- 2.9
```

Same model; the paper reports a 21.8-point spread (79.8 down to 58.0) -- a range it notes is "comparable to differences between model generations". [verified: live tbench.ai/leaderboard/terminal-bench/2.0 probed first-hand 2026-07-05] Eight of the nine rows match the live board exactly (Capy 75.3 through Claude Code 58.0); **ForgeCode/79.8 -- the top of the spread -- is NOT on the live board** (142 entries checked; also absent from the 2.1 board, which has since moved to Opus 4.7/4.8, not 4.6). So the paper's headline 79.8 top and 21.8-pt figure cannot be confirmed at the primary today: either ForgeCode was withdrawn since the paper's snapshot or mis-attributed in it. The **live-verifiable spread is 75.3 -> 58.0 = 17.3 points** on one fixed model. The thesis survives the correction intact and is in fact independently corroborated on the same site: the 2.1 board shows a Claude Opus 4.7 -> 4.8 generation gap of roughly 9-13 points -- *smaller* than the 17.3-point harness spread. The harness moved the score more than a model generation did.

### Fix: Treat Every Single-Number Model Claim as Under-Specified

- A benchmark or leaderboard score attributed to a model alone is a claim about a system with the system half redacted. Before acting on "model X beats model Y", check whether the harness was held constant; if it wasn't, you are comparing two systems, not two models.
- The harness you operate -- CLAUDE.md gates, hooks, skills, memory files, verification loops -- is a performance component of model-generation magnitude, not process bureaucracy. This table is the external empirical grounding for that premise.
- When an agentic tool underperforms, the harness layer is a suspect of the same rank as the model. Interrogate scaffold, context assembly, and stop conditions before concluding "the model got worse" (pairs with Example 16: diagnose at the layer that actually failed).

### Provenance and Caveats (kept, because they bound the claim)

- Primary source reached and extracted directly: arxiv.org/html/2606.17799 fetched, Table 1 parsed. The social corpus cited two inconsistent arXiv IDs (2606.10209 vs 2606.17799); both were probed and the wrong one eliminated -- the trust rule in action, resolve the ID before citing.
- Position paper by a vendor whose commercial thesis is that current benchmarks are broken. The table data is TerminalBench leaderboard compilation, not the authors' own runs.
- Leaderboard rows are per-org submissions; run configs (token budgets, retries, parallelism) are not normalized. The spread is real on the live leaderboard; its causal decomposition (pure harness design vs submission-config differences) is not established by the numbers alone. [verified: tbench.ai 2.0 probed 2026-07-05 -- 8/9 rows confirmed, ForgeCode/79.8 top row absent from the live board, so cite the 17.3-pt live spread, not the paper's 21.8; the ForgeCode row is paper-only until the leaderboard shows it again.]
- The paper's prose says "four agent harnesses" against its own 9-row table -- an editing artifact. Cite the table, not the prose.

### Pairing With Other Patterns

- Example 5 (Ground Truth Verification): the score you can verify is the system's, not the model's -- state which system.
- Example 7 (Bot Reviews Need Verification): a confident number gets traced to its primary source before it shapes a decision.
- Lesson 11 (badge != outcome): a leaderboard rank is a badge; the outcome is behaviour under YOUR harness. Benchmark on your own stack before switching models on the strength of someone else's number.
- Lesson 24 (summary-layer upgrades): this same paper's finding was inflated from "comparable" to "harness > model" by a downstream brief -- the two entries are the same incident seen from the source side and the artifact side.

## 22. The "Not Sponsored" Disclosure That Was Also an Ad

### Problem: Disclosure Verified True, Incentive Never Recorded

Two tutorial videos enter a content-ingestion pipeline as sources of build-workflow claims. Both carry explicit no-sponsorship disclosures, and both verify TRUE against the transcripts ("Not Affiliated Or Sponsored By ..."; "None Of The Videos Are Sponsored So All The Tools That I'll Be Sharing You Are Just Because I Use Them"). The skeptic pass marks the disclosure claim verified-true and moves on. But both videos funnel viewers, repeatedly, to one product site -- and the creator narrates the funnel as his own growth technique ("provide value first, then put the call to action inside of description"). A product-launch registry names him the product's maker, in his own words.

Nothing here is false. "Not sponsored" is literally true -- nobody paid him. But the videos are, structurally, lead generation for a product he owns, and every tool recommendation ingested from them now carries an implicit "disinterested source" tag it never earned.

### Fix: Verify the Disclosure AND Trace the Funnel Ownership

"No third-party sponsorship" and "no commercial incentive" are independent states -- track them separately, the same way Lesson 13 tracks migrated and rotated as independent states for a leaked secret. Verifying one does not discharge the other.

Concrete probes, one per state:

1. Disclosure state: grep the transcript for the disclosure and pin the line numbers.
2. Incentive state: list every product/URL the source funnels to, then run an ownership probe on each -- fetch the product page (an owner-less product page is signal, not absence), then a launch/registry source (maker section, launch post). A funnel target owned by the source = first-party incentive.
3. Record the incentive as source metadata ("author owns <funnel target>; videos double as lead-gen") so every downstream claim ingested from that source inherits the tag and gets weighted accordingly -- especially the source's tool choices and "just because I use them" recommendations.

[verified: operator authenticated X read + first-hand Product Hunt fetch, 2026-07-05] The author-to-maker linkage is pinned: the creator's own verified X account (@viktoroddy) posts "Free Access to AI prompts ... motionsites.ai. Also, Motionsites is live on Product Hunt" -- a direct funnel to the product -- and the Product Hunt maker section reads verbatim "Viktor Oddy here, creator of MotionSites". Two independent reachable cross-links (the account's own promotion + the registry's maker attribution) confirm the video author owns the funnel target, so the "not sponsored" videos are first-party lead-gen for a product he makes. (Original inferential basis -- name match + the maker comment + the funnels -- held; this just closed it with the primary. Archive the PH maker section, as it is the load-bearing ownership source and can change.)

### Heuristic

A no-sponsorship disclosure scopes exactly one incentive channel: third-party payment. The trigger for the ownership probe is any recurring funnel to a named product in "not sponsored" content. Literally-true disclosure + first-party funnel = the content is an advertisement for the funnel target; ingest its claims with the incentive tag attached, never as disinterested testimony.
