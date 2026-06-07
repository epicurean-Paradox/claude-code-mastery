# Global Engineering Standards — ~/CLAUDE.md
#
# Universal rules for ALL projects under your home directory.
# Project-specific CLAUDE.md files add to these; they never override them.

---

## Code Quality

- Single responsibility: each function/module does one thing well.
- Explicit over implicit — name variables and functions so intent is obvious.
- Handle errors at boundaries (user input, external APIs); trust internal logic.
- Keep functions short. If it needs scrolling, split it.
- Surgical changes only: do not refactor or clean up code outside current task scope.

## Security Fundamentals

- All secrets in `.env` — never hardcoded, never logged, never in CLI args.
- Always use HTTPS for external services.
- Set explicit timeouts on all outbound HTTP calls (connect + read).
- Exponential backoff with jitter for retries; no retry on 4xx (except 429).
- Validate and sanitize all data from external APIs.
- Verify signatures on incoming webhooks before processing.
- Principle of least privilege for all service accounts.

## Git Conventions

- `main` is always deployable — no direct commits.
- Feature branches: `feature/<short-name>`, `fix/<short-name>`.
- Commit format: `type(scope): short description` (imperative mood).
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
- Subject line under 72 characters. Body only if the *why* is non-obvious.
- One PR = one concern. Squash merge into `main`.

## Environment

- `.env.example` with placeholders as documentation. Never commit `.env`.
- Validate required env vars at startup; fail fast with clear message.

## Testing

- Test any logic with branching behavior (conditions, retries, parsing).
- Prefer real integrations; mock only external services with unstable availability.
- Tests must pass before merging to `main`.

## Dependencies

- Pin versions in lockfiles and commit them.
- Review changelogs before upgrading, especially for breaking changes.
- Audit periodically. Remove unused dependencies promptly.

## Session Continuity

When a session hits context limit, the continuation summary MUST include:
1. What was completed (with verification: counts, timestamps, test results).
2. What's next (specific task, not vague direction).
3. Any blockers or decisions pending user input.

Do NOT start work in a continuation session until reading project context files.


## Branch & PR Pipeline

Extends "Git Conventions". One PR = one concern still holds; these sharpen *how you sequence and stage the work*.

### Branch from fresh main, every time

- Right before each new PR: `git checkout main && git pull`, then branch. Never branch off a stale local `main` or accidentally off another feature branch.
- One branch = one concern. Never reuse a branch for an unrelated change, even a one-liner — open a new branch from fresh `main`.

### Sequence-dependent PRs

- When two PRs touch overlapping files, **merge the first before branching the second.** Branching the second off pre-merge `main` guarantees stacked-conflict churn at merge time (seen with `intake.py` / `set_status` across consecutive PRs).
- If the work genuinely can't wait for the merge, branch off the first branch and rebase after it merges — treat that as the exception, not the default.

### Cross-repo / cross-service features

- Sequence so the **enabling change merges first**: the receiving endpoint before the caller, the schema before the writer, the consumer before the producer.
- **Gate runtime on config** so the not-yet-deployed half no-ops. The deployed-but-unused half must carry zero risk: off by default, flipped on only once both sides are live.
- For a shared secret: generate it on one side, copy it to the other's secret store. Never commit it; never log it.

### Staging the commit

- gitignored artifacts (`coverage.xml`, `*.tfvars` with real values, build output) MUST NEVER be staged. `git status` before every commit; `git restore --staged` / `git clean` anything ignored that slipped in.
- CI is the gate, not local hooks — `git push --no-verify` is fine when a local hook is slow or flaky. The required checks decide mergeability.

### CI flake discipline

- A required check that mass-`ERROR`s at **fixture/setup** on a **single matrix leg** (testcontainers/Docker won't start, one language version) is a flake, not your bug. **Re-run the failed job.**
- Distinguish "tests *ran* and *asserted* false" (your bug) from "tests never started" (infra flake) before touching anything. Do not edit code to chase a green you can't explain.

### CD / infra hygiene

- Keep the deploy queue clean: cancel superseded or parked deploy runs so the latest commit isn't blocked behind dead ones.
- ALWAYS confirm the target before `apply`/`destroy`: `terraform workspace show`. Acting in the wrong workspace is silent and expensive.
- Review every `destroy` plan resource-by-resource and confirm **zero** cross-env / cross-project resources before applying. A destroy plan that names anything outside the intended scope is a stop, not a prompt.

### Response gate

- Before a PR is "ready": every bot comment (Gemini, Claude auto-review, any reviewer) gets either a fix commit or an inline reply referencing the fix commit. See LESSONS Lesson 1 — the severity gate decides what blocks merge; the response gate decides what you owe the reviewer.

## Multi-agent / Ultracode Usage

Ultracode (the Workflow multi-agent engine) is **opt-in only**. It can spawn dozens of agents — token cost scales with agent count. Spin it up only when one of these is true, and never infer scale the user did not ask for:

- The user types the keyword `ultracode`.
- The user explicitly asks to "use a workflow" or "fan out agents".
- A skill the user invoked calls it.

### Fit-for-parallel, not serial

Parallelism is a property of the *work*, not a speed dial — it only buys speed when the units are independent.

- **Good fits** (parallel / broad / adversarial / scale): multi-perspective review councils (N domain reviewers + one synthesis pass), exhaustive adversarial audits (finders surface, skeptics refute, majority vote decides), completeness sweeps (plan-vs-code, every-modality), broad mechanical migrations across many files.
- **Bad fits** (sequential / gate-bound / judgment-heavy): cross-repo wiring, deploy-gated steps, anything where stage N needs stage N-1's verified result. Fanning out a serial chain pays orchestration overhead without moving the real bottleneck (human review, CI, deploy gates). Keep these single-threaded.

### Lightweight vs heavy

- **Plain Agent tool** (a few parallel subagents you synthesize) is the default — enough for a review council or quick multi-perspective pass.
- **Workflow engine** is reserved for heavier exhaustive / looping passes where the orchestration itself (barriers, voting, loop-until-dry) is load-bearing.

### Patterns

- **Pipeline-by-default** — no barrier between stages unless a stage genuinely needs ALL prior results.
- **Adversarial verify** — skeptics must refute, not rubber-stamp; a majority of skeptics kills a finding.
- **Loop-until-dry** — re-run finders until a pass produces nothing new.
- **Completeness critic** — a dedicated agent checks coverage, not correctness.
- **Multi-modal sweep** — one agent per modality / surface.
- Scale agent count and verification depth to how thorough the user asked for — not to how thorough you could be.

### Cost honesty

When a workflow bounds coverage (top-N findings, sampling, no-retry, capped agent count), say so explicitly and name what was dropped. The user decides whether bounded coverage is acceptable — do not silently present a partial sweep as exhaustive.
