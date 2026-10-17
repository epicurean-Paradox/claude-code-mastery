# instrument schema -- instruction-graph@1

An instrument is a markdown file with a `---`-fenced YAML frontmatter block. The
body is prose (read, never machine-bound); the frontmatter is validated data. One
file per instrument; a directory of them is the graph. `README.md` is skipped.

Frontmatter:

```yaml
id: pipeline-rule                       # required, unique, identifier-shaped; reuse an existing namespace
title: All data operations ...          # required, short
layer: project                          # required; ordered authority vocabulary (see below)
type: rule                              # required; rule|lesson|gate|protocol|objective|narrative
status: active                          # required; active|superseded|withdrawn|proposed
enforcement:                            # required for type in {rule, lesson, gate}
  kind: ci                              #   hook|ci|test|pre-pr-checklist|none
  ref: .github/workflows/ci.yml::job    #   resolvable reference; required unless kind: none
  state: live                           #   live|declared|absent
links:                                  # optional; typed, directional
  refines: [naming-protocol]
owner: data-platform                    # optional provenance
applies_to: in-repo                     # optional; in-repo|machine-local
source: HANDBOOK.md#pipeline@abc1234    # optional; resolvable provenance stamp
last_reviewed: 2026-10-17               # optional
review_stale_after_days: 180            # optional
```

| Field | Required | Rules |
|---|---|---|
| `id` | yes | Unique, identifier-shaped (`^[A-Za-z0-9][A-Za-z0-9_.-]{0,96}$`). Reuse an existing namespace; do not fork a parallel id scheme. |
| `title` | yes | Short sentence-case. |
| `layer` | yes | In the ordered authority vocabulary. Default: `org-global > team > project > session > memory`. An implementation pins its own ordered list and passes it to the validator. Order is load-bearing (see I8). |
| `type` | yes | `rule`, `lesson`, `gate`, `protocol`, `objective`, `narrative`. Only the first three require enforcement. `narrative` is the escape hatch for frozen prose. |
| `status` | yes | `active`, `superseded`, `withdrawn`, `proposed`. A `superseded` instrument must name `superseded_by`; a `withdrawn` one must name `withdrawn_reason` -- withdrawn instruments stay as tombstones, never deleted, so the correction trail survives. |
| `enforcement` | for rule/lesson/gate | `{kind, ref, state}`. `kind: none` forces `state: absent` (making "no enforcement is an open defect" machine-visible). A non-`none` kind needs a non-empty `ref`. `state`: `live` = runs in CI (an implementation's binding test can exercise it); `declared` = a committed machine-local enforcer, confirmed present but not confirmed firing; `absent` = none yet. The validator checks shape, never that the enforcer fires -- that is the implementation's binding test. |
| `links` | no | Mapping of verb -> list of ids. Verbs: `supersedes`, `refines`, `derived_from` (a DAG -- cycles are an error), `enforces`, `enforced_by`, `conflicts_with` (exempt from the cycle check; a `conflicts_with` resolved by a `supersedes` is a legitimate cycle). Every target must resolve to a known instrument id. A same-layer `conflicts_with` must be broken by an explicit `supersedes`. |
| `owner`, `applies_to`, `source`, `last_reviewed`, `review_stale_after_days` | no | Provenance and review metadata. An unknown top-level key is an error (additionalProperties: false). |

Validator exit codes: 0 = pass (warnings allowed), 1 = any error, 2 = file/dir
unreadable. Zero instruments parsed exits 1 (fail-closed).

Input limits (an input boundary, so it bounds its own inputs): each file is read
in a bounded prefix (64 KiB) so a large prose body is never slurped; frontmatter
over 16 KiB is rejected; any YAML alias (`*name`, in block or flow syntax) is
refused before values are built, because `safe_load` still expands aliases and a
tiny alias file can reach gigabytes. A field of the wrong type (a list where a
string belongs) is a coded error, never a crash. Every output line is a single
line of at most 240 characters with control characters escaped.
