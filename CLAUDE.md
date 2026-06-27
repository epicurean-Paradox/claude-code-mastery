# Claude Code Mastery — Core Skill

This file encodes a methodology for high-quality, consistent Claude Code sessions. Drop it into any project or install as a skill.

---

## Layered Configuration

Claude Code loads CLAUDE.md files hierarchically. Use all three layers:

1. **`~/.claude/CLAUDE.md`** — Private global. Communication style, personal preferences. Never committed.
2. **`~/CLAUDE.md`** — Home-level global. Engineering standards that apply to every project: code quality, security, git conventions, testing.
3. **`<project>/CLAUDE.md`** — Project-specific. Architecture rules, skill trigger tables, session protocols, domain context.

Each layer adds. No layer repeats another. If a rule applies everywhere, it goes in the global. If it applies to one project, it goes in that project's file.

**Anti-pattern**: one massive CLAUDE.md mixing universal rules with project-specific protocols. This wastes context and causes Claude to treat project rules as universal.

---

## Session Start Protocol

At the start of every session (new or continuation), Claude MUST:

1. Read project context files (plan, backlog, handoff notes) before responding.
2. State the current work context: active phase, known blockers, next task.
3. Ask the user to confirm before starting work.

This prevents the cold-start problem where Claude makes assumptions about what to work on.

```markdown
## Session Start (template for your project CLAUDE.md)

**FIRST ACTION** in any session:
1. Read `PROJECT_PLAN.md` for current phase and priorities
2. State: current phase, known blockers, what was last done
3. Ask: "Ready to continue with [current task]?"
```

---

## Session Decay Prevention

After 10-15 turns, Claude stops checking docs, drifts from architecture, and takes shortcuts. This is not a bug — it's context window pressure.

**Counter-measure**: add a periodic self-audit:

```markdown
Every 10 responses OR when switching tasks:
1. Re-read the project plan
2. Verify current work aligns with stated priorities
3. If drifted: "Refocusing on [X] per project plan"
```

Claude will follow this because it appears in every context window refresh. The key is making it a numbered checklist, not prose.

---

## Context Limit Continuity

When a session hits the context limit, Claude generates a summary. Without structure, that summary is useless.

**Fix**: embed a continuation block in your project CLAUDE.md:

```markdown
When this session reaches context limit, the summary MUST start with:

=== CONTINUATION START ===
Before continuing:
1. Read HANDOFF.md (what was done, what's next)
2. Read PROJECT_PLAN.md (current phase)
3. State: current phase, blockers, next task
Do NOT work until these steps are complete.
=== END ===
```

The next session sees this block first and self-orients.

---

## Skill Security Gate

Before any community skill enters a project's trigger table, it MUST pass all three security audits on [skills.sh](https://www.skills.sh/):

| Audit | Required result |
|-------|----------------|
| Gen Agent Trust Hub | PASS |
| Socket | PASS |
| Snyk | PASS |

**WARN = rejected. FAIL = rejected. Only PASS on all three.**

**Enforcement**: before adding ANY skill to a trigger table, WebFetch `https://www.skills.sh/<org>/<repo>/<skill-name>` and extract the Security Audits section. If any audit is not PASS, reject the skill and suggest an alternative. Do not skip this check.

This is non-negotiable. A skill with a Snyk WARN may have known vulnerabilities in its dependency tree. A Socket WARN may indicate supply-chain risk. Do not override this gate for convenience.

---

## Skill-Driven Workflows

Map task types to **security-vetted** skills in a trigger table. Check the table before every response.

**Mandatory skills** (block work until invoked):
- Security audit before any PR
- SQL injection check for user-input queries

**Recommended skills** (strong default, skip with reason):
- `/python-pro` for Python refactors
- `/sql-pro` for SQL queries
- `/database-design` for schema changes

```markdown
## Skill Gate

| Task type                     | Skill              | Required? | Audits |
|-------------------------------|---------------------|-----------|--------|
| Pre-PR security review        | `/security-audit`   | MANDATORY | 3/3 PASS |
| Writing SQL                   | `/sql-pro`          | Recommended | 3/3 PASS |
| Python pipeline code          | `/python-pro`       | Recommended | 3/3 PASS |
| Database migration            | `/database-migrations-sql-migrations` | Recommended | 3/3 PASS |
```

**Key insight**: "invoke the skill BEFORE writing code" must be explicit. Without this, Claude writes code first and retrofits the skill's advice — which defeats the purpose.

When adding a new skill to the trigger table, verify its audit status first. Document the check date in a comment so stale audits get rechecked.

---

## Ground Truth Verification

Never trust documentation about system state. Always verify:

| Claim type | Verification |
|------------|-------------|
| "Table X exists" | Run `\d table_name` |
| "Table has N rows" | Run `SELECT COUNT(*) FROM table` |
| "Function X is defined in file Y" | Read the file or grep |
| "API returns format Z" | Make the call |
| "Last pipeline ran at T" | Query execution logs |
| "Pushed" | `git ls-remote` SHA == local HEAD (a clean `push` exit is not proof) |
| "My fix is in main" | `git show origin/main:<path>` contains the fix (not the MERGED badge) |
| "Merged, therefore deployed/applied" | Confirm the deploy run / infra apply actually fired |
| "Deployed, therefore working" | Observe the live surface render/respond |
| "Endpoint exists, therefore done" | A client actually calls it (wiring is a separate axis) |
| "It has a passing test, therefore it's done" | Read what the test *asserts* and compare to the *intended* behaviour -- a test written from observed output pins the regression as the contract. See LESSONS Lesson 16 |
| "I couldn't find it" | Only after searching the *full* corpus (e.g. all `~/.claude/projects/<project>/*.jsonl`); a partial search yields a false "not found". See LESSONS Lesson 15 |

**Rule**: if you can verify it in 5 seconds, verify it. Don't cite memory or docs.

**Verify every state transition, not just claims.** A green upstream signal (a clean `push`, a MERGED badge, a successful build) reports a step was *attempted* -- never that the *downstream state* now holds. Each "therefore" between two gates is an unverified assumption until probed. See LESSONS Lesson 11.

**Subagent trust boundary.** A subagent reading source is authoritative about *what is wired* (what exists, what calls what) and only inferential about *what is true at runtime*. Trust its structural findings; verify its "empty / broken / missing" claims against live state before acting. "No cron exists" is not "the table is empty." See LESSONS Lesson 12.

---

## Fix It, Don't Flag It

When you discover a defect while doing something else -- a masked CI failure, a silently-broken test, a disabled gate, a latent bug -- repair it (its own branch/PR if it's out of the current scope), don't park it in a status update. The "honest advisor" stance is for challenging assumptions and surfacing trade-offs, not for narrating a defect you could have fixed. Mentioning a broken thing without fixing or filing it wastes the discovery.

This is distinct from the response gate on review comments: that's about owing the *reviewer* a reply; this is about owing the *codebase* a fix.

**A lesson that isn't a gate gets re-violated.** When a retro produces a lesson, name the mechanism that will enforce it -- a CLAUDE.md gate, a pre-PR checklist line, a hook, a test, an auto-loading memory entry. Prose does not execute; a lesson with no enforcement is a hope, and hopes decay into re-violations (this repo's Lesson 3 and Lesson 5 were both re-violated in one session despite being written). Treat "this lesson has no enforcement mechanism" as an open defect, not a finished retro. See LESSONS Lesson 17.

---

## The lesson loop is enforced, not hoped (LEDGER.md + hooks/)

Distillation and recall do not close the loop on their own -- the failure mode of Lesson 17. Two ends are now mechanized:

- **Enforcement (write time).** `hooks/prototype-scaffold-guard.sh` is a PreToolUse hook (matcher `Write|Edit|MultiEdit`) that blocks design-prototype scaffold (a state-gallery stepper, reviewer nav hints, `StageLabel` banners) from landing in first-party frontend source -- the Lesson 3 violation, now failing loud instead of shipping.
- **Detection (session start).** `hooks/lesson-loop-audit.sh` is a SessionStart hook that greps the live frontend tree for scaffold already shipped and counts the SOFT (ungated) rows in `LEDGER.md`, so re-violations and open defects surface without a human noticing.

`LEDGER.md` is the spine: every lesson is classified HARD / SEMI / SOFT by *how it is enforced*. A LESSONS entry with no ledger row, or a SOFT row with no named "next gate", is itself a Lesson-17 open defect. Install: copy `hooks/*.sh` to `~/.claude/hooks/` and register them in `~/.claude/settings.json` under `PreToolUse` (`Write|Edit|MultiEdit`) and `SessionStart`. Not every lesson can or should be HARD -- judgment-heavy ones (L11/L15/L16) get a forced checklist plus the detection audit; the ledger makes that choice explicit rather than pretending all lessons are gateable.

---

## Environment & Tooling Footguns

An agent shell is not an interactive terminal with a human watching resource usage. A few defaults are unsafe:

- **Never background a file-watching dev server** (`next dev`, `vite`, `nodemon`, `tsc --watch`). The runtime stops tracking a backgrounded process after the turn, nothing reaps it, and a watcher rooted at the wrong directory grows without bound (one leaked past 65 GB RAM). To probe a dev server, start + curl + kill in one compound command, or let the test runner own its lifecycle. Sweep `pgrep` / `docker ps` at session end.
- **Never use `sed` / `perl -0pi` for source edits that may contain non-ASCII.** Stream editors carry no UTF-8 guarantee and corrupt multibyte characters (em-dash, section sign) into mojibake. Use the structured edit tool.
- **Prefer literal absolute paths.** `~` / `expanduser` can resolve to the cwd, not home. When stdout looks duplicated or truncated, write to a temp file and read it back. NFC-normalise macOS filenames before matching. Don't move a parent of the working directory mid-session while relying on relative paths.

See LESSONS Lesson 14.

---

## Pre-Response Checklist

Before every response in a project with active development:

1. **Skill gate**: does this task match a trigger? Invoke first.
2. **Phase check**: does this work align with current priorities?
3. **Architecture compliance**: does the approach follow project patterns?
4. **Documentation**: will the project plan need updating after this?
5. **Ambiguity**: if unclear, ask — don't assume.

---

## Communication Principles

- State results and decisions directly. No preambles, no trailing summaries.
- When referencing code, include `file:line` for navigation.
- Challenge weak reasoning. Call out assumptions.
- If a task seems wrong, say so before executing.
- Professional writing. No filler words. No emojis unless requested.
