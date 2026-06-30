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
- **`diagnosis-evidence-audit.sh`** (SessionStart digest / Stop / CI) -- scans recent
  transcripts for the Lesson-2 shape: a causal / external-suspect diagnosis ("snapshot",
  "deploy", "stale", "race", "242 vs local") asserted with no source-of-truth probe and
  no `[hypothesis:]` tag. Surfaces the re-violation a regex over *code* can't (the defect
  lives in *prose*, not the tree). Self-tested in `hooks/test-fixtures/`.

## The ledger

| # | Lesson | Tier | Enforcement mechanism (or next gate if SOFT) |
|---|--------|------|----------------------------------------------|
| 1 | Severity gate is not the response gate | SEMI | Branch-protection conversation-resolution gate (HARD for thread-resolution) + CLAUDE.md PR-pipeline steps 6/7 |
| 2 | A diagnosis that "matches" an external suspect is not diagnosed (generalised: any causal claim about a discrepancy -- bug, failed step, or two numbers that disagree) | **SEMI + HARD-detect** | Ground-Truth causal-claim row + `[verified:]`/`[hypothesis:]` forcing format on diagnoses (SEMI, read every response) + `hooks/diagnosis-evidence-audit.sh` transcript scan (HARD detection). **Built 2026-06-29** after the lesson re-fired on a £527K-vs-£625K renewal figure; the "next gate" had sat unbuilt for a year (a live Lesson-17 case). Irreducibly judgment-heavy like L11/L15/L16 -- HARD *prevention* is the wrong target; forced format + detection is the honest close |
| 3 | Distinguish dev assets from desired outcome | **HARD** | `~/.claude/hooks/prototype-scaffold-guard.sh` (PreToolUse Write/Edit/MultiEdit) blocks scaffold tokens in `frontend/src` |
| 4 | Multi-account CLI hygiene | SEMI | Memory `reference_github_credentials` (auto-load) + dir-scoped `gh()` wrapper |
| 5 | Memory is the durable layer | SEMI | SessionStart loads `MEMORY.md`; *next gate*: a session-end "did any decision go uncaptured?" check |
| 6 | Branch from fresh main; re-run flakes | SEMI | `pre-commit` branch-validation (HARD for branch name) + SOFT for the re-run-don't-chase judgment |
| 7 | Multi-agent is opt-in | SEMI | CLAUDE.md ultracode gate (keyword-triggered) |
| 8 | Convene a skill council; ground the names | SOFT | *Next gate*: a "names grounded against code?" checklist line for load-bearing design |
| 9 | Long-running tasks need a worktree on a shared dir | SEMI | Memory `feedback_worktree_isolation_concurrent_sessions` (auto-load) |
| 10 | A documented merge process is not an enforced one | **HARD** | `main` branch protection (9 strict checks + conversation-resolution), since 2026-06-16 |
| 11 | The green badge is not the outcome | SOFT | CLAUDE.md Ground-Truth table (checklist). *Next gate*: per-claim verify is judgment; covered by the SessionStart audit + the verify checklist |
| 12 | Trust a subagent's "what is wired", verify "what is broken" | SOFT | *Next gate*: a verify step before acting on a subagent "empty/missing" claim |
| 13 | A migrated secret is still a leaked secret | SEMI | `secret-scanner.sh` (PreToolUse) + gitleaks blocking CI (HARD for committed secrets); rotation-tracking is SOFT |
| 14 | The dev server you backgrounded is still running | SOFT | **Mechanizable -- next gate**: a PreToolUse Bash guard that blocks `next dev`/`vite`/`tsc --watch` with `run_in_background`/`&` |
| 15 | Accuracy outranks token-frugality on a retrieval request | SOFT | CLAUDE.md Ground-Truth "couldn't find" row + memory `feedback_accuracy_over_token_conservation`. *Next gate*: behavioral; the SessionStart audit demonstrates exhaustive scope |
| 16 | A green test can certify the wrong behaviour | SOFT | CLAUDE.md Ground-Truth "passing test != done" row + memory `feedback_test_asserts_intended_not_shipped`. *Next gate*: per-feature -- rewrite the asserting test (e.g. FI-3) so CI fails on the regression |
| 17 | A lesson that isn't a gate gets re-violated | **HARD** | **This ledger** + the SessionStart audit that counts SOFT rows. A new lesson with no `Enforcement` cell is an open defect by construction |

## Cadence

- Add a row here in the SAME change that adds a LESSONS entry. A LESSONS entry without
  a ledger row is itself a Lesson-17 violation.
- Re-run the full re-derivation audit (the multi-agent frontend/plan sweep) periodically;
  promote SOFT rows to HARD as cheap mechanizations are found (L14 is the next candidate).
- Goal is not "all HARD" -- some lessons are irreducibly judgment-heavy (L11, L15, L16).
  For those, HARD is the wrong target; a forced checklist + the detection audit is the
  realistic close. The ledger's job is to make that choice explicit, not to pretend.
