---
id: naming-protocol
title: Branch and artifact naming protocol
layer: org-global
type: protocol
status: active
owner: platform
applies_to: in-repo
source: HANDBOOK.md#naming@abc1234
last_reviewed: 2026-10-17
review_stale_after_days: 365
---

# Branch and artifact naming protocol

Worked example for a fictional org, "Acme Metrics". A protocol instrument carries
no enforcement (it is guidance, not a gate), so it declares no `enforcement`
block and the validator does not require one. Other instruments point at it with
`refines` / `derived_from`; it has no outgoing links of its own, so the validator
reports it as a W1 ORPHAN -- a warning, not an error, because a root node that is
only ever a link target is legitimate.
