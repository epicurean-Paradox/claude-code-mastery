# Claude Code Mastery

A battle-tested system for getting consistently high-quality work from Claude Code across sessions, projects, and teams.

Most Claude Code guides teach you *what to say*. This one teaches you **how to architect your entire Claude Code environment** so the AI stays sharp, focused, and aligned — even after 50+ turns in a session.

---

## The Problem

Claude Code is powerful out of the box. But in real-world projects:

- **Session drift**: after 15-20 turns, Claude forgets your conventions and starts improvising.
- **Context loss**: when a session hits the context limit, the continuation starts from scratch.
- **Config sprawl**: one giant CLAUDE.md tries to cover everything — bot security, database patterns, frontend conventions — and none of it sticks.
- **Inconsistent quality**: Claude solves the same problem differently each session because there's no persistent methodology.

This system fixes all of that.

---

## Five Pillars

### 1. Layered Configuration

Stop putting everything in one file. Claude Code loads CLAUDE.md files hierarchically:

```
~/.claude/CLAUDE.md        ← Private global (communication style, personal prefs)
~/CLAUDE.md                ← Home-level global (engineering standards for ALL projects)
~/project/CLAUDE.md        ← Project-specific (architecture, skill triggers, protocols)
```

All layers merge. Each adds specificity without repeating the layer above.

**Why it works**: A bot project and a data pipeline project need completely different rules. But they both need your security standards and git conventions. Layer once, specialize per project.

See [templates/](templates/) for ready-to-use files at each layer.

### 2. Session Continuity Protocol

When Claude hits the context limit, it generates a summary for the next session. Without a protocol, that summary is vague and the continuation session starts blind.

**The fix**: embed a continuation block that forces the next session to read context files before doing anything:

```markdown
## Context Limit Protocol

When this session reaches context limit, the summary MUST start with:

=== CONTINUATION SESSION START ===
Before continuing, you MUST:
1. Read [PROJECT_PLAN.md] for current phase and priorities
2. Read [HANDOFF.md] for what was done and what's next
3. State current phase, known blockers, and next task

Do NOT start work until these 3 steps are complete.
=== END ===
```

The continuation session sees this as its first instruction and orients itself before writing code.

### 3. Session Decay Prevention

Even within a single session, Claude's adherence to your rules degrades after many turns. It stops checking docs, drifts from the architecture, and starts taking shortcuts.

**The fix**: add a periodic reset trigger:

```markdown
## Session Decay Prevention

Every 10 responses OR when switching tasks:
1. Re-read PROJECT_PLAN.md current phase
2. Verify alignment with stated priorities
3. If drifted, state: "Refocusing on [current phase] per project plan"
```

This creates a self-correcting loop. Claude audits itself instead of silently degrading.

### 4. Skill-Driven Workflows

Claude Code has hundreds of community skills on [skills.sh](https://www.skills.sh/). The problem: you have to remember to invoke them, and not all of them are safe.

**Security gate**: before any skill enters your trigger table, verify it passes all three security audits on skills.sh:

| Audit | Required |
|-------|----------|
| Gen Agent Trust Hub | PASS |
| Socket | PASS |
| Snyk | PASS |

**WARN or FAIL on any audit = skill rejected.** No exceptions.

**Automated enforcement**: instruct Claude Code to WebFetch `https://www.skills.sh/<org>/<repo>/<skill>` and extract the Security Audits section before adding any skill to a trigger table. If any audit is not PASS, the skill is rejected automatically.

Then map vetted skills to task types in a **trigger table**, checked before every response:

```markdown
## Skill Gate (runs BEFORE any code)

| Task type                  | Invoke first         | Audits |
|----------------------------|----------------------|--------|
| Writing SQL                | `/sql-pro`           | 3/3 PASS |
| Pre-PR security review     | `/security-audit`    | 3/3 PASS |
| Database migration         | `/database-migrations-sql-migrations` | 3/3 PASS |
| Refactoring Python         | `/python-pro`        | 3/3 PASS |
```

Make security skills **mandatory** (non-negotiable gate). Make others **recommended** (strong default, override with reason).

### 5. Ground Truth Verification

Claude confidently claims things that aren't true — tables that don't exist, functions that were renamed, row counts from stale docs.

**The fix**: force verification before any claim:

```markdown
## Ground Truth

Before making ANY claim about system state:
- Database: run the query, don't cite documentation
- Files: check they exist, don't assume from memory
- APIs: verify endpoints respond, don't trust old docs
- Never say "the table has X rows" without running SELECT COUNT(*)
```

This single rule eliminates the most dangerous Claude Code failure mode: confident hallucination about your own codebase.

---

## Patterns That Surfaced Later

Battle-tested additions from real multi-PR sessions. Same shape as the Five Pillars (problem → fix → why) but learned in the field rather than designed up front. See [EXAMPLES.md](EXAMPLES.md) for full write-ups.

### 6. The Rationalization Detector

When Claude (or you) files something as *"valid drift / documented divergence / defensible design choice,"* run two tests first:

1. Does it violate a written ADR? → gap, not drift.
2. Is it the lone exception to a sweep that touched every sibling? → gap, not drift.

Either fires → promote to a Known Gap with concrete action items. Real session score: 3 of 5 items filed as "valid drift" were rationalizations.

### 7. Bot Reviews Need Verification, Not Obedience

Trivial mechanical bot suggestions (typos, missing imports, encoding fixes) apply as-is. **Semantic** suggestions — *"X is a no-op," "this is dead code," "this invariant holds"* — need a 60-second verification against the language spec or a microtest before applying. The phrase *"X always does Y"* is the verification trigger.

Real example: a bot's "redundant `move_to_end`" claim almost shipped an LRU-eviction bug because `OrderedDict.__setitem__` doesn't reorder existing keys (only appends new ones).

### 8. Documentation Cadence

Plans rot in 9 days. Make doc-sync a standing rule, not a virtue: after every 5 merged PRs, audit `MASTER_PROJECT_PLAN.md` and `README.md` against `git log --since=<plan_last_updated>`. Any capability-surface delta that the docs don't cover → open a `docs/<short-description>` PR.

The audit IS the work. Plan PRs are a legitimate output of the autonomous loop, not a chore.

### 9. FastAPI Override Request-Injection Footgun

When overriding a FastAPI dependency that takes `request: Request`, the type annotation **must** use a module-scope canonical `from fastapi import Request`. Aliased or function-local imports trip FastAPI's signature introspector → 422 with `loc:[query, request]` instead of an injected Request.

Generalizes to any framework doing signature introspection on overrides.

### 10. The Test-Suite Inclusion Gate

"Add more tests" feels like a no-cost win. It isn't — every suite that lives in CI rents attention forever. Before adding any new test suite, dependency, or testing-tool, run it through five tests:

1. **Concrete-gap** — name a recent PR or bug where its absence bit you
2. **Consumer** — a workflow / gate / human actually reads the signal today
3. **Substitution** — the signal isn't already arriving from somewhere else (bot reviewer, type checker, existing test)
4. **Prerequisite** — the surface it measures actually exists (deployed env, rendered component, populated DB)
5. **Volume** — callsite count justifies the abstraction overhead

All five pass → INCLUDE. Any one fails → DEFER with a written trigger that names the failing test + the precondition that flips it. Worked sweep: 4 candidates (testing-library, coverage-v8, schemathesis, vitest-axe) INCLUDED; 4 (Storybook, Stryker, k6, MSW) DEFERRED with explicit triggers.

The gate resists session-enthusiasm drift: the same five tests applied next month would produce the same verdicts. Failing candidates aren't forgotten — they're carried as Known Gaps with the exact precondition that flips them.

### 11. Delegation Poker for AI Loops

The default delegation level is NOT *"AI decides, then informs you."* Most substantive work — multi-PR sweeps, architecture changes, deploys, non-trivial refactors — sits at level 3-5 ("Consult / Agree / Advise"), not level 7 ("Delegate"). Codify the level at task entry; default to **Consult** when unclear; re-confirm whenever directives shift.

Specific failure mode this names: the **stale schedule**. A scheduled wake-up (cron / `ScheduleWakeup` / `/loop`) carries a prompt that pre-dates the operator's most-recent directive. When the wake-up fires, treat the directive as authoritative — pause, surface the conflict, ask which read of intent governs. Do NOT execute the stale prompt on autopilot.

### 12. The Build/Ship Gravity Trap

An autonomous PR loop's reward function is *"produce a reviewable, mergeable artifact."* Deploy work produces no such artifact until it succeeds — and one URL when it does. Result: 14 small PRs land while zero deploys happen. Eight reinforcing biases (iteration speed, reviewable artifacts, risk asymmetry, access friction, "CODE COMPLETE = done," no CI alarm, role assumption, no named trigger) point the gradient at code, never at deploy.

Mechanical fix: a `deploy-gate.yml` workflow that blocks `feat/*` PRs from merging until a repo variable (`AWS_INFRA_BOOTSTRAPPED=true`, set by the first successful deploy) flips. `chore/`, `fix/`, `docs/`, `test/`, `refactor/` flow through unchanged. Bypass label for the single PR that IS the bootstrap enabler. Generalizes anywhere build and ship are decoupled (library releases, migration application, test infra wiring).

### 13. Observability Before Autonomy

CloudWatch / Prometheus / Datadog capture *signals*. They do not capture *agency*. An AI working from the repo can write infrastructure-as-code but cannot, without a deliberate harness, query the running infrastructure-as-system. Every operational issue becomes a manual `aws logs tail` paste — the exact friction the autonomy was meant to remove.

Build the inspection harness *at the same time* as the IaC: a `inspect.yml` manual-dispatch workflow that queries CloudWatch + ECS state, a `drift-detect.yml` scheduled `terraform plan`, a `smoke.yml` periodic curl, a `rollback.yml` one-button, a read-only MCP runtime-query tool, an admin `/runtime-status` endpoint, and GitHub Actions → AWS OIDC trust (no long-lived keys). H1 + H7 are the unlock — once both exist, "what's broken?" gets answered from the repo, not from a paste.

### 14. Auth Surface Separation

Same vendor, two tokens. The product runtime uses cloud-native IAM (AWS Bedrock, Azure OpenAI, GCP service accounts). The CI / dev tooling uses the vendor's hosted-action OAuth or API key. Different network paths, different cost centres, different audit trails — but the natural assumption ("we use vendor X" = "one auth path") sends debuggers to the wrong file every time.

Real instance: CI's auto-review job failed with *"ANTHROPIC_API_KEY: empty."* The product uses Bedrock — no Anthropic key needed anywhere in the deployed stack. The failure was upstream-action-internal, not auth. The intuition that "Bedrock everywhere = no keys anywhere" delayed the right diagnosis by an hour.

Codify the two surfaces explicitly in CLAUDE.md (which IAM grant for product, which secret for CI). When a vendor-auth bug surfaces, identify the surface *first*: failure in CI = check the CI secret; failure in production = check the IAM grant. Pairs with Pattern 7 (verify bot suggestions before applying — the bot may be flagging the wrong surface).

---

## Quick Start

### Option A: Full system (recommended)

Copy the three template files into position:

```bash
# Global engineering standards (all projects)
curl -o ~/CLAUDE.md https://raw.githubusercontent.com/epicurean-Paradox/claude-code-mastery/main/templates/global.md

# Private preferences (communication style, personal rules)
mkdir -p ~/.claude
curl -o ~/.claude/CLAUDE.md https://raw.githubusercontent.com/epicurean-Paradox/claude-code-mastery/main/templates/private-global.md

# Project-specific (copy into each project, then customize)
curl -o ./CLAUDE.md https://raw.githubusercontent.com/epicurean-Paradox/claude-code-mastery/main/templates/project.md
```

### Option B: Just the CLAUDE.md

Drop the core skill file into any project:

```bash
curl -o CLAUDE.md https://raw.githubusercontent.com/epicurean-Paradox/claude-code-mastery/main/CLAUDE.md
```

### Option C: Claude Code skill

```bash
claude skill add --from github epicurean-Paradox/claude-code-mastery
```

---

## Templates

| File | Purpose | Location |
|------|---------|----------|
| [templates/private-global.md](templates/private-global.md) | Communication style, personal prefs | `~/.claude/CLAUDE.md` |
| [templates/global.md](templates/global.md) | Engineering standards for all projects | `~/CLAUDE.md` |
| [templates/project.md](templates/project.md) | Project-specific rules, skill triggers | `<project>/CLAUDE.md` |

---

## Examples

See [EXAMPLES.md](EXAMPLES.md) for real before/after scenarios showing each pillar in action.

---

## Lessons learned (in the wild)

See [LESSONS.md](LESSONS.md) for real incidents from running this system on production projects, the rule changes they motivated, and the generalisable patterns behind them. Append new lessons there as they land — the accumulating list is the value.

---

## Contributing

Open an issue or PR. The best contributions are **real-world patterns** you've battle-tested across multiple sessions — not theoretical improvements.

---

## License

MIT
