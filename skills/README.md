# Skills

Vendored skills that pair with the patterns in this repository. Each skill ships
as plain markdown (a `SKILL.md`), consistent with this repo's zero-runtime model:
patterns and skills you adopt, not services you install.

## Vendoring rules

A candidate is vendored here only if it ships as a markdown/pattern artifact with
no runtime, service, daemon, port, or data store. Tools that ship a runtime
(memory daemons, vector DBs, agent platforms) are referenced as external tools,
never bundled.

Every vendored skill preserves its upstream license and records its provenance
below.

## Vendored skills

| Skill | Upstream | License | Source commit | Retrieved |
|---|---|---|---|---|
| [handoff](handoff/SKILL.md) | [mattpocock/skills](https://github.com/mattpocock/skills/tree/main/skills/productivity/handoff) | MIT (c) 2026 Matt Pocock — see [handoff/LICENSE](handoff/LICENSE) | `d54c497aa94400a496d3f2c38be10fa5f284c5a9` | 2026-06-09 |

### handoff

Compacts the current conversation into a transfer document so a fresh agent can
resume work: references existing artifacts by path instead of duplicating them,
suggests skills for the receiving agent, and redacts secrets. Complements the
Session Continuity Protocol pattern in [../CLAUDE.md](../CLAUDE.md).
