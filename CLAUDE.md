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

That block covers the *cross-session* boundary. The SDK also compacts **in-session**: when the context window fills, it automatically summarizes older turns mid-session, and instructions from early in the conversation may not survive. Two consequences. Durable rules belong in CLAUDE.md, never only in the opening prompt — CLAUDE.md is re-injected (and prompt-cached) every request, so it survives compaction; the opening prompt is one-shot and gets summarized away. And you can steer the compactor: add a `## Summary instructions` block to the project CLAUDE.md naming what to preserve (current objective + acceptance criteria, file:line anchors touched, last probe/test results, decisions, open Known Gaps). The compactor reads CLAUDE.md like any other context, so it honors the list. This is the real fix for the decay that the deleted "re-read every 10 responses" rule only pretended to address.

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
| "A differs from B **because** Z" / "X broke because of `<snapshot / deploy / stale cache / timing / race / environment>`" | Probe the source of truth that *adjudicates* the discrepancy **before** stating the cause (the upstream report, the authoritative log, a clean-room repro). A cause that *fits* the gap is not the cause that's been *shown* -- that gap is the whole of Lesson 2. Unprobed, it is a hypothesis: write it `[hypothesis: <cheapest probe>]`, never as a finding. See LESSONS Lesson 2 |
| A design / plan / council **names** a file, function, or skill | `grep` / Read that the symbol exists in the tree before building on the name. An ungrounded name is a design resting on a guess (and a recalled memory naming a file is only as fresh as when it was written -- re-verify). See LESSONS Lesson 8 |
| "There's no X" / "the table is empty" / "couldn't find it" (an **absence** claim) | A negative needs a *full* search, not a partial one (L15), and a subagent's "empty/missing" is inferential -- verify it against live state before acting (L12). "No cron exists" is not "the table is empty." Tag the scope you searched `[searched: <scope>]`. See LESSONS Lessons 12, 15 |

**Rule**: if you can verify it in 5 seconds, verify it. Don't cite memory or docs.

**Verify every state transition, not just claims.** A green upstream signal (a clean `push`, a MERGED badge, a successful build) reports a step was *attempted* -- never that the *downstream state* now holds. Each "therefore" between two gates is an unverified assumption until probed. See LESSONS Lesson 11.

**Subagent trust boundary.** A subagent reading source is authoritative about *what is wired* (what exists, what calls what) and only inferential about *what is true at runtime*. Trust its structural findings; verify its "empty / broken / missing" claims against live state before acting. "No cron exists" is not "the table is empty." See LESSONS Lesson 12.

**A diagnosis is a claim too -- tag it or probe it (forcing format).** The Ground-Truth rows above all guard *state* claims ("pushed", "merged", "table exists"). The one category that slips every state-check is the **causal** claim: "the difference is a snapshot", "it broke because of the deploy", "that's just stale data". A plausible mechanism reads as a verified one -- that is precisely how Lesson 2 recurs. So a causal / external-suspect diagnosis carries an inline evidence tag or it is not stated as fact:

- `[verified: <probe>]` -- you ran the probe that adjudicates it (queried the upstream source, reproduced in a clean room, read the authoritative log).
- `[hypothesis: <cheapest probe>]` -- you have not, and here is the one cheap check that would confirm or kill it.

Tagging a real finding is one phrase; tagging a guess `[verified]` is a lie you will not write -- so the honest path (`[hypothesis]`) is also the cheap one. An **untagged** bare external-cause diagnosis is the defect. The forcing function that actually catches this in practice: *before you write the cause, write the evidence line that proves it* -- if you can't, it's a hypothesis. (This is what catches it when a diagnosis goes into external comms; the rule pulls that check earlier, to every causal claim.) Detection backstop: `hooks/evidence-audit.sh` scans transcripts for untagged causal/external diagnoses and surfaces them. See LESSONS Lesson 2 + LEDGER row 2.

---

## Fix It, Don't Flag It

When you discover a defect while doing something else -- a masked CI failure, a silently-broken test, a disabled gate, a latent bug -- repair it (its own branch/PR if it's out of the current scope), don't park it in a status update. The "honest advisor" stance is for challenging assumptions and surfacing trade-offs, not for narrating a defect you could have fixed. Mentioning a broken thing without fixing or filing it wastes the discovery.

This is distinct from the response gate on review comments: that's about owing the *reviewer* a reply; this is about owing the *codebase* a fix.

**A lesson that isn't a gate gets re-violated.** When a retro produces a lesson, name the mechanism that will enforce it -- a CLAUDE.md gate, a pre-PR checklist line, a hook, a test, an auto-loading memory entry. Prose does not execute; a lesson with no enforcement is a hope, and hopes decay into re-violations (this repo's Lesson 3 and Lesson 5 were both re-violated in one session despite being written). Treat "this lesson has no enforcement mechanism" as an open defect, not a finished retro. See LESSONS Lesson 17.

---

## The lesson loop is enforced, not hoped (LEDGER.md + hooks/)

Distillation and recall do not close the loop on their own -- the failure mode of Lesson 17. Two ends are now mechanized:

- **Enforcement (write time).** `hooks/prototype-scaffold-guard.sh` is a PreToolUse hook (matcher `Write|Edit|MultiEdit`) that blocks design-prototype scaffold (a state-gallery stepper, reviewer nav hints, `StageLabel` banners) from landing in first-party frontend source -- the Lesson 3 violation, now failing loud instead of shipping.
- **Enforcement (call time).** `hooks/dev-server-guard.sh` is a PreToolUse hook (matcher `Bash`) that blocks a file-watching dev server (`next dev` / `vite` / `nodemon` / `tsc --watch` / `*run dev`) launched with `run_in_background` or a trailing `&` -- the Lesson 14 footgun (an unreaped watcher leaked past 65 GB RAM), now failing loud. Foreground start+probe+kill is allowed.
- **Detection (session start).** `hooks/lesson-loop-audit.sh` is a SessionStart hook that greps the live frontend tree for scaffold already shipped and counts the SOFT (ungated) rows in `LEDGER.md`, so re-violations and open defects surface without a human noticing.
- **Detection (transcript).** `hooks/evidence-audit.sh` scans recent transcripts for three claim shapes the state-checks miss: **causal** diagnoses (Lesson 2 -- "snapshot", "deploy", "242 vs local" stated as fact), **absence** claims (Lessons 12 + 15 -- "couldn't find", "no such cron", "empty"), and **state-chain** claims (Lesson 11 -- "merged so it's live"), each flagged only when untagged and unprobed. Suppression differs by family: causal clears only on an inline tag/probe (turn-level probing the *wrong* source was the L2 failure), absence/state clear on any probe that turn. SessionStart digest / Stop hook / `--file` (exit 1) modes; self-tested in `hooks/test-fixtures/` (flags the real "527K is the 242 snapshot" turn, passes the tagged rewrite).
- **Preservation (pre-compaction).** `hooks/precompact-archive.sh` is a PreCompact hook that snapshots the full transcript to `~/.claude/precompact-archives/` before the SDK summarizes older turns. Without it the detection audits above go blind at the moment of greatest information loss: they read `~/.claude/projects/*.jsonl`, which in-session compaction summarizes away. The archive keeps pre-compaction history readable for the audits and for a human.

`LEDGER.md` is the spine: every lesson is classified HARD / SEMI / SOFT by *how it is enforced*. A LESSONS entry with no ledger row, or a SOFT row with no named "next gate", is itself a Lesson-17 open defect. Install: copy `hooks/*.sh` **and `hooks/*.py`** (the audit ships as a thin `.sh` dispatcher + a `.py` engine -- both must land together) to `~/.claude/hooks/`, then register in `~/.claude/settings.json`: `prototype-scaffold-guard.sh` (matcher `Write|Edit|MultiEdit`) and `dev-server-guard.sh` (matcher `Bash`) under `PreToolUse`; `lesson-loop-audit.sh` and `evidence-audit.sh` under `SessionStart`; `evidence-audit.sh --stop` under `Stop` (the tight loop -- block finishing on an untagged/unprobed causal, absence, or state claim, loop-guarded via `stop_hook_active`); `precompact-archive.sh` under `PreCompact` (snapshot the transcript before compaction summarizes it away). CI (`.github/workflows/lesson-gates.yml`) runs every hook's self-test so the gates can't silently rot. Not every lesson can or should be HARD -- judgment-heavy ones (L11/L15/L16) get a forced checklist plus the detection audit; the ledger makes that choice explicit rather than pretending all lessons are gateable.

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
