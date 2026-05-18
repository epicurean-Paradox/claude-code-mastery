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

## Contributing

Open an issue or PR. The best contributions are **real-world patterns** you've battle-tested across multiple sessions — not theoretical improvements.

---

## License

MIT
