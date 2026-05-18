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
