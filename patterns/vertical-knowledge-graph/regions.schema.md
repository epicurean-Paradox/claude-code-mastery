# regions.yaml schema — vertical-knowledge-graph@1

Top level:

```yaml
pattern: vertical-knowledge-graph@1     # required, exact
verticals: [revenue, gtm, product, development, customer, people-ops, finance]
                                        # required; the closed vocabulary for this org
stale-after-days: 14                    # default evidence freshness window (per-region override allowed)
regions: []                             # required, may be empty only with a reason: key
```

Per region (one entry per vertical that has any presence — a vertical with no
region entry is DARK by definition and the validator reports it):

| Field | Required | Rules |
|---|---|---|
| `vertical` | yes | Must be in the top-level `verticals` vocabulary. One region per vertical. |
| `status` | yes | `observed` or `declared-only`. `observed` requires a complete, fresh `evidence` block. |
| `sources` | yes | List of `{name, category, health?}`. `category` from: crm, marketing, ticketing, vcs, chat, hr, conversation-intelligence, product-analytics, billing, winloss, docs, other. May be empty only when `status: declared-only` (a thin/aspirational region). |
| `entities` | yes | Business objects the region asserts knowledge about (accounts, deals, tickets, …). |
| `destinations` | yes | Tables/collections the region's data lands in. Empty allowed only with `status: declared-only`. |
| `sensitivity_tier` | yes | Integer 1–4, 1 = most sensitive. Cross-region edges (future versions) inherit the lower number (higher sensitivity) of their endpoints. |
| `rbac.scope` | yes | Intended read scope string, e.g. `graph:read:revenue`. |
| `rbac.enforced` | yes | Boolean. `true` additionally requires `rbac.enforcement_point` naming the code choke point. |
| `rbac.enforcement_point` | when enforced | Path/identifier of the resolver enforcing the scope. |
| `consumers` | yes | List of `{name, recurring_question}`. Empty ⇒ validator marks the region DEFERRED (warning, and an error if `status: observed`). |
| `evidence` | when observed | `source-health` (map source→`healthy@<date>`), `row-counts` (map destination→int>0), `last-run` (`{id, at}`), `verified-at` (date), `describes-commit` (sha). Any missing key ⇒ error. `verified-at` older than the freshness window ⇒ demoted, error. |
| `erasure_lineage` | conditional | Required (`subject_key` naming the deletion key) when any source category is `conversation-intelligence` or `hr`. |
| `notes` | no | Free text. |

Validator exit codes: 0 = pass (warnings allowed), 1 = any error, 2 = file/schema
unreadable. A validator that parsed zero regions exits 1 (fail-closed).
