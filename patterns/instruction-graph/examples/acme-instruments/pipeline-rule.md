---
id: pipeline-rule
title: All data operations run through the orchestrator
layer: project
type: rule
status: active
enforcement:
  kind: ci
  ref: .github/workflows/ci.yml::architecture
  state: live
owner: data-platform
applies_to: in-repo
links:
  refines: [naming-protocol]
source: HANDBOOK.md#pipeline@abc1234
last_reviewed: 2026-10-17
review_stale_after_days: 180
---

# All data operations run through the orchestrator

A `rule` instrument must declare `enforcement`. Here the enforcer runs in CI
(`state: live`), so an implementation's own binding test can exercise it against a
violating fixture. The reference validator only checks the reference is
well-shaped; proving it fires is the implementation's test, not the pattern's.
