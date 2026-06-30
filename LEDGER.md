# Lesson Enforcement Ledger

This file operationalizes **Lesson 17 -- a lesson that isn't a gate gets re-violated.**
Every lesson is classified by *how it is enforced*, not just whether it is written.
A lesson whose only enforcement is "prose someone may re-read" is an **open defect**,
not a closed retro.

## Enforcement tiers

- **HARD** -- a mechanism executes regardless of attention and fails loud on violation
  (a hook in `~/.claude/settings.json`, a `.git/hooks/pre-commit` check, a required CI
  check / branch-protection rule, a test that fails on the regression).
- **SEMI** -- active only if a trigger is matched or a checklist is read
  (the CLAUDE.md skill-gate / PR-pipeline checklist, a memory entry that auto-loads).
  Narrows the gap; still attention-dependent.
- **SOFT** -- prose only (CLAUDE.md / memory / LESSONS). Necessary so the knowledge
  exists; insufficient as enforcement. **= open defect; carries a "next gate".**

## Detection (the other open end)

Distillation and recall do not close the loop if nobody notices the re-violation.
Two detection mechanisms now run without depending on the operator noticing:

- **`prototype-scaffold-guard.sh`** (PreToolUse) -- blocks the L3 violation at write time.
- **`lesson-loop-audit.sh`** (SessionStart) -- each session, greps first-party frontend
  for scaffold tokens already in the tree and prints the count of SOFT (ungated) lessons
  from this ledger, so the open defects stay visible.
- **`evidence-audit.sh`** (SessionStart digest / Stop / CI) -- one engine, three rule
  families over the transcript: **causal** diagnoses (Lesson 2 -- "snapshot", "242 vs
  local"), **absence** claims (Lessons 12/15 -- "couldn't find", "empty"), **state-chain**
  claims (Lesson 11 -- "merged so it's live"), each flagged untagged + unprobed.
  Suppression is per-family (causal clears only on an inline tag/probe; absence/state on
  any probe that turn). Surfaces re-violations a regex over *code* can't -- the defect
  lives in *prose*, not the tree. Self-tested in `hooks/test-fixtures/`. (Merged from the
  former diagnosis-evidence-audit + claim-evidence-audit pair, 2026-06-30.)
- **`dev-server-guard.sh`** (PreToolUse `Bash`) -- *enforcement*, not detection: blocks a
  backgrounded file-watching dev server at call time (Lesson 14, the 65 GB leak).

## The ledger

| # | Lesson | Tier | Enforcement mechanism (or next gate if SOFT) |
|---|--------|------|----------------------------------------------|
| 1 | Severity gate is not the response gate | SEMI | Branch-protection conversation-resolution gate (HARD for thread-resolution) + CLAUDE.md PR-pipeline steps 6/7 |
| 2 | A diagnosis that "matches" an external suspect is not diagnosed (generalised: any causal claim about a discrepancy -- bug, failed step, or two numbers that disagree) | **SEMI + HARD-detect** | Ground-Truth causal-claim row + `[verified:]`/`[hypothesis:]` forcing format on diagnoses (SEMI, read every response) + `hooks/evidence-audit.sh` transcript scan (HARD detection). **Built 2026-06-29** after the lesson re-fired on a £527K-vs-£625K renewal figure; the "next gate" had sat unbuilt for a year (a live Lesson-17 case). Irreducibly judgment-heavy like L11/L15/L16 -- HARD *prevention* is the wrong target; forced format + detection is the honest close |
| 3 | Distinguish dev assets from desired outcome | **HARD** | `~/.claude/hooks/prototype-scaffold-guard.sh` (PreToolUse Write/Edit/MultiEdit) blocks scaffold tokens in `frontend/src` |
| 4 | Multi-account CLI hygiene | SEMI | Memory `reference_github_credentials` (auto-load) + dir-scoped `gh()` wrapper |
| 5 | Memory is the durable layer | SEMI | SessionStart loads `MEMORY.md`; *next gate*: a session-end "did any decision go uncaptured?" check |
| 6 | Branch from fresh main; re-run flakes | SEMI | `pre-commit` branch-validation (HARD for branch name) + SOFT for the re-run-don't-chase judgment |
| 7 | Multi-agent is opt-in | SEMI | CLAUDE.md ultracode gate (keyword-triggered) |
| 8 | Convene a skill council; ground the names | **SEMI** | CLAUDE.md Ground-Truth row "a design names a file/function/skill -> grep/Read it exists in the tree". Judgment-heavy (a name-existence hook over prose is too noisy to be honest HARD); the read-every-response checklist is the close. Built 2026-06-30 |
| 9 | Long-running tasks need a worktree on a shared dir | SEMI | Memory `feedback_worktree_isolation_concurrent_sessions` (auto-load) |
| 10 | A documented merge process is not an enforced one | **HARD** | `main` branch protection (9 strict checks + conversation-resolution), since 2026-06-16 |
| 11 | The green badge is not the outcome | **SEMI + HARD-detect** | CLAUDE.md Ground-Truth table (pushed/merged/deployed rows) + `hooks/evidence-audit.sh` narrow state-chain detection ("merged so it's live" with no probe this turn). Built 2026-06-30 |
| 12 | Trust a subagent's "what is wired", verify "what is broken" | **SEMI + HARD-detect** | CLAUDE.md Ground-Truth subagent-boundary + absence row + `hooks/evidence-audit.sh` absence detection (adopting "empty/missing/none" with no probe this turn). Built 2026-06-30 |
| 13 | A migrated secret is still a leaked secret | SEMI | `secret-scanner.sh` (PreToolUse) + gitleaks blocking CI (HARD for committed secrets); rotation-tracking is SOFT |
| 14 | The dev server you backgrounded is still running | **HARD** | `hooks/dev-server-guard.sh` (PreToolUse `Bash`) blocks `next dev`/`vite`/`nodemon`/`tsc --watch`/`*run dev` with `run_in_background` or a trailing `&`; foreground start+probe+kill allowed. Built 2026-06-30 |
| 15 | Accuracy outranks token-frugality on a retrieval request | **SEMI + HARD-detect** | CLAUDE.md Ground-Truth "couldn't find"/absence rows + memory `feedback_accuracy_over_token_conservation` + `hooks/evidence-audit.sh` absence detection (flags "couldn't find" with no search tool-call that turn). Built 2026-06-30 |
| 16 | A green test can certify the wrong behaviour | **SEMI** | CLAUDE.md Ground-Truth "passing test != done" row + memory `feedback_test_asserts_intended_not_shipped`. Per-feature judgment (no honest global HARD); the gate is the read-what-it-asserts checklist + the per-feature test rewrite that fails on the regression. Built 2026-06-30 |
| 17 | A lesson that isn't a gate gets re-violated | **HARD** | **This ledger** + the SessionStart audit that counts SOFT rows. A new lesson with no `Enforcement` cell is an open defect by construction |

## Cadence

- Add a row here in the SAME change that adds a LESSONS entry. A LESSONS entry without
  a ledger row is itself a Lesson-17 violation.
- Re-run the full re-derivation audit (the multi-agent frontend/plan sweep) periodically;
  promote SOFT rows to HARD as cheap mechanizations are found (L14 is the next candidate).
- Goal is not "all HARD" -- some lessons are irreducibly judgment-heavy (L11, L15, L16).
  For those, HARD is the wrong target; a forced checklist + the detection audit is the
  realistic close. The ledger's job is to make that choice explicit, not to pretend.
