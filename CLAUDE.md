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

To verify: go to `https://www.skills.sh/<org>/<repo>/<skill-name>` and check the Security Audits section. If any audit shows WARN or FAIL, the skill is not eligible — find an alternative or build your own.

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

**Rule**: if you can verify it in 5 seconds, verify it. Don't cite memory or docs.

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
