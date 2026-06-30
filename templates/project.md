# Project-Specific Instructions — <project>/CLAUDE.md
#
# Customize this template for each project.
# It layers ON TOP of ~/CLAUDE.md (global) and ~/.claude/CLAUDE.md (private).
# Only include rules specific to THIS project.

---

## Project Context

# Describe the project in 1-2 sentences so Claude understands the domain:
# This is a [type of project] that [what it does] for [who].

## Architecture Rules

# Define the patterns Claude MUST follow in this project:
# - [e.g., All data operations go through the pipeline orchestrator]
# - [e.g., No standalone scripts — everything is a stage]
# - [e.g., All API routes must use the middleware chain]

## Session Start Protocol

**FIRST ACTION** in any session:
1. Read `PROJECT_PLAN.md` for current phase and priorities
2. State: current phase, known blockers, what was last done
3. Ask: "Ready to continue with [current task]?"

Do NOT start work until these steps are complete.

## Summary instructions

# Read by the IN-SESSION compactor: when the context window fills, the SDK
# automatically summarizes older turns mid-session and early instructions can be
# lost. It reads this CLAUDE.md, so it preserves what is listed here. (Durable
# rules belong in this file, re-injected every request, not only in the opening
# prompt, which is one-shot and gets summarized away.)
When summarizing this conversation, always preserve:
- The current task objective and its acceptance criteria
- File:line paths read or modified this session
- The last test / probe results and any error messages
- Decisions made and the reasoning behind them
- Open Known Gaps and the current phase from PROJECT_PLAN.md

## Context Limit Protocol

When this session reaches context limit, the summary MUST start with:

```
=== CONTINUATION START ===
Before continuing:
1. Read HANDOFF.md (what was done, what's next)
2. Read PROJECT_PLAN.md (current phase)
3. State: current phase, blockers, next task
Do NOT work until these steps are complete.
=== END ===
```

## Skill Security Gate

Every skill in the trigger table MUST pass all 3 audits on skills.sh before inclusion:
- Gen Agent Trust Hub: PASS
- Socket: PASS
- Snyk: PASS

WARN or FAIL on any = rejected.

**Enforcement**: before adding ANY skill to a trigger table, WebFetch `https://www.skills.sh/<org>/<repo>/<skill>` and extract the Security Audits section. If any audit is not PASS, reject the skill and suggest an alternative. Do not skip this check.

## Skill Triggers

# Customize this table for your project's tech stack.
# MANDATORY skills block work until invoked. Recommended skills are strong defaults.
# Only include skills that pass all 3 security audits (see gate above).

| Task type                     | Skill                    | Required?   | Audits  |
|-------------------------------|--------------------------|-------------|---------|
| Pre-PR security review        | `/security-audit`        | MANDATORY   | 3/3 PASS |
| Writing SQL                   | `/sql-pro`               | Recommended | 3/3 PASS |
| Python code                   | `/python-pro`            | Recommended | 3/3 PASS |
| Database migration            | `/database-migrations-sql-migrations` | Recommended | 3/3 PASS |
# Add more rows for your stack... verify audits first.

If you are about to write code and did not check the trigger table: STOP. Check it. Invoke if matched. Then proceed.

## Ground Truth

Before making ANY claim about system state:
- Database: run the query, don't cite documentation
- Files: check they exist, don't assume from memory
- APIs: verify endpoints respond, don't trust old docs


## Branch & CI Discipline

- Branch from fresh `main` every PR: `git checkout main && git pull`, then branch. When two PRs touch the same files, merge the first before branching the second.
- A required check that mass-`ERROR`s at fixture/setup on one matrix leg (Docker/testcontainers, one language version) is a flake — re-run the job, don't edit code to chase it.
- `terraform workspace show` before any `apply`/`destroy`; review destroy plans for cross-env/cross-project resources.

## Multi-agent

- Ultracode is opt-in only (keyword `ultracode`, an explicit "use a workflow" request, or a skill that calls it). Use it for parallel/broad/adversarial work, not serial gate-bound chains. See global.md "Multi-agent / Ultracode Usage".
