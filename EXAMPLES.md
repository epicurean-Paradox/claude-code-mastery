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
