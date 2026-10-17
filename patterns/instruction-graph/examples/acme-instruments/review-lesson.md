---
id: review-lesson
title: A lesson that names no enforcer gets re-violated
layer: team
type: lesson
status: active
enforcement:
  kind: hook
  ref: hooks/review-guard.sh
  state: declared
owner: eng-leads
applies_to: machine-local
links:
  derived_from: [naming-protocol]
source: RETRO-2026-10.md#L3@abc1234
last_reviewed: 2026-10-17
review_stale_after_days: 180
---

# A lesson that names no enforcer gets re-violated

A `lesson` must name a resolvable enforcer. This one points at a machine-local
hook, so its `state` is `declared`, not `live`: the enforcer is committed but no
CI job runs it, so the in-repo validator can confirm it is present but not that
it fires. `declared` is the honest middle state; claiming `live` for a hook that
does not run in CI is the badge-is-not-the-outcome defect the schema exists to
prevent.
