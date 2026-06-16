# Lessons Learned (in the wild)

Real failure modes encountered while running this system on production projects, with the rule changes they motivated. Each lesson follows the same shape: what happened, what was wrong with the response, what changed in the system, and the generalisable pattern.

When a new lesson lands in your environment, append it here -- the value of the doc is in the specifics, not the abstractions.

---

## Lesson 1 -- Severity gate is not the response gate

### What happened

Across one project's last eight merged PRs, an audit found **65 unaddressed bot review comments**. Reviewers were Gemini Code Assist and the Claude Code Action `auto-review` job. Among the unaddressed comments:

- 1 finding tagged `[HIGH] A01 broken access control` -- an admin view rendered for any authenticated user; gating banner was cosmetic; mock data today but the codebase shape locked in a real bug for the next phase.
- 4 findings tagged `Medium` -- a silent auth-bypass: `AuthProvider` swallowed `/auth/session` network errors and a downstream guard `authEnabled && !authenticated` evaluated to `false` on the error path, letting unauthenticated users through.

Each of these had been visible on the PR for hours before merge. None had a reply, none had a fix commit.

### What was wrong with the response

The existing rule said: *"HIGH / sec-HIGH findings are blocking; MEDIUMs addressed unless explicitly justified."* That rule is a **severity gate** -- it decides what blocks merge. It was being read as a complete policy, so non-blocking comments got silently ignored.

Worse, the HIGH finding on the admin-view PR should have blocked merge under the old rule too. It didn't, because nobody (human or assistant) was systematically walking the inline-comment list before clicking merge.

### What changed in the system

The PR processing pipeline gained a **response gate** alongside the severity gate:

> **Address EVERY inline comment** -- not just HIGH / sec-HIGH. Low, Suggestion, Nit, and unlabelled bot comments must each get either (a) a follow-up commit that addresses the finding, or (b) an inline reply with a one-sentence justification for not addressing it. Silently merging with unaddressed bot comments is a process violation.
>
> The severity gate decides *what blocks merge*. The response gate decides *what you owe the reviewer*. Bot reviewers (Gemini, Claude auto-review) are part of the team -- their signal degrades if non-blocking comments are routinely ignored.

The check ("every bot comment from step N has either a fix-commit or an inline reply") was added as an explicit gate in the merge-checklist, just before the rebase-and-merge step.

### Generalisable pattern

Two separate questions live on every comment thread:

1. **Does this block merge?** Severity rule answers this.
2. **Did the author respond?** Response rule answers this.

Conflating the two reliably produces both `unaddressed-non-blocking` debt (which decays reviewer signal) and the rare but expensive `unaddressed-blocking` accident (because nobody was enumerating).

Make them two separate gates. Codify the enumeration step.

---

## Lesson 2 -- A bug that "matches" an external suspect is not diagnosed

### What happened

After logging in via Cognito Hosted UI + Google IdP, users on a production deployment kept landing on `https://localhost:3000/` (Chrome HTTPS-First mode showed a cert error). A HAR-style export of the failing flow showed three Chrome extensions injecting content scripts on the page:

- 1Password (`aeblfdkhhhdcdjpifhhbdiojplfjncoa`)
- QuillBot
- "Console Events Recorder"

A request to `https://localhost:3000/` appeared in the HAR with `Referer: https://throughline-dev.datamaran.com/`. The extension theory matched: 1Password probes local apps, the localhost fetch sits adjacent to extension script fetches, the user already had local Grafana running on port 3000.

The assistant pinned the bug on the extensions and recommended toggling them off.

### What was wrong with the response

The user retested in **Brave incognito with all extensions disabled** and reproduced the localhost hop. The extension theory was dead on arrival -- there were no extensions in that browser session.

The real cause was in app code: the OAuth callback handler used

```ts
NextResponse.redirect(new URL(returnTo, req.url));
```

Behind the load balancer, the Next.js standalone server received `req.url` with host `http://localhost:3000` (the internal container listener). `new URL("/", "http://localhost:3000/auth/callback?...")` resolved to `http://localhost:3000/`, and the 302 `Location` header carried that to the browser.

The extensions were a red herring. The HAR happened to contain extension fetches because the user's normal browser had extensions; they were unrelated to the bug.

### What changed in the system

A diagnostic rule was promoted before pinning any bug on a browser, network, or environment-level suspect:

> When a bug *looks* like it could be an extension / network / proxy / OS issue, reproduce it in a clean-room first: incognito session of a different browser, all extensions disabled. Only after the clean-room reproduces the bug do you consider environment-level causes. Until then, the bug lives in app code by default.

And specifically for any framework that hides the proxy from the app:

> Behind a reverse proxy / load balancer, `req.url` carries the **internal** listener host, not the public host. Never use `req.url` as the base for redirects, links, or anything user-facing. Derive the public origin from an operator-controlled, proxy-validated value (in OAuth flows: the configured `redirect_uri` env var, which the identity provider's allow-list validates).

### Generalisable pattern

A diagnosis that *fits the evidence* is not the same as a diagnosis that *explains all the evidence*. Pattern-matching on the most visually salient anomaly (extension scripts in a HAR) skips the falsification step.

Always run the clean-room reproduction before committing to an external-suspect diagnosis. The cost is one private-window session; the cost of being wrong is hours of mis-routed remediation and an unfixed production bug.

---

## Lesson 3 -- Distinguish dev assets from desired outcome

### What happened

A design prototype lived in the repo as a hash-routed single-page mockup (`workspace.html`, `view_*.jsx`, `agent_states.jsx`). The prototype was richly annotated:

- a top-of-page stepper labelled `End-user / Non-happy / Admin-only`
- a "← → to navigate" keyboard-hint pill
- `StageLabel` banners on each mocked state ("HAPPY ・ 01", "WARN ・ 02")
- inline commentary blocks describing what each state demonstrated

Porting the prototype to production, the assistant translated everything 1:1, including the stepper, the keyboard hint, the StageLabel banners, and the commentary blocks. The production deployment shipped with the developer-facing annotations visible to end users.

The user's feedback was direct: *"You literally included in the app the user journey nav and all views declared there. Which is like taking a wireframe prototype and developing the designer comments and each and all of the mockup messages and data."*

### What was wrong with the response

A design prototype contains **two layers**: the artefact being designed (the actual UI for the user) and the dev-reference scaffold around it (annotations, state pickers, captions explaining what the reader is looking at). The 1:1 port collapsed them. The result was a UI that talked to its developer audience instead of its end users.

### What changed in the system

A new pre-port checklist now lives in the relevant project's CLAUDE.md:

> When porting a design prototype to production:
>
> 1. Enumerate every element on the prototype page. For each one, ask: is this *part of the artefact* or *part of the dev reference around the artefact*?
> 2. Dev-reference indicators: state pickers, stepper labels naming flows, keyboard hint pills, commentary captions, "HAPPY / WARN / ERROR" badges, anything addressed to the prototype's reader rather than to the product's user.
> 3. Default rule: dev-reference elements DO NOT ship to production. If you are unsure whether an element is artefact or reference, ask -- do not copy.

### Generalisable pattern

Any artefact that's meant to *demonstrate* a UI -- mockups, Figma frames, prototype HTML, screenshot annotations -- is bigger than the UI it demonstrates. The wrapper exists to communicate intent to the design audience. It is not part of what ships.

Treat 1:1 fidelity to the prototype as a code-smell, not a goal. The thing the prototype *describes* is what should ship, not the prototype itself.

---

## Lesson 4 -- Multi-account CLI hygiene

### What happened

The same machine had two GitHub identities authenticated in `gh` CLI keyring: a work identity (org member, write access to employer repos) and a personal identity (owner of personal/public repos including the very system docs being updated). Both were active in the keyring; only one was "Active account" at a time.

When updating an issue tracker on the work org, the personal account was active. When trying to push to the personal repo, the work account was active. Each write call against the wrong identity either failed with `push: false` or risked posting under the wrong actor (a hard-to-undo public action).

### What was wrong with the response

The assistant treated `gh` as a single-identity tool and skipped the `gh auth status` check before write actions. Permission errors surfaced as confusing failures (`could not add label`, `403 push denied`) instead of being predicted and prevented.

### What changed in the system

A reference rule for any multi-identity CLI environment:

> Before every `gh` write action (`gh issue create`, `gh pr create`, `gh api -X POST`, `git push` against a repo with provider-side identity tracking), check the active account:
>
> ```bash
> gh auth status | grep -A1 "Active account: true"
> ```
>
> If the target repo's org does not match the active account's accessible orgs, switch:
>
> ```bash
> gh auth switch -u <account>
> ```
>
> Verify again before proceeding. Write actions under the wrong identity are public and hard to undo cleanly.

The same pattern applies to AWS profile switching, kubectl contexts, Terraform workspaces -- anywhere "which identity am I acting as" is hidden behind a single command name.

### Generalisable pattern

CLI tools default to a single active identity but quietly support several. The convenience is also the foot-gun: the same command does completely different things depending on hidden state. Make "which identity am I" an explicit pre-action check, not a debugging step after a confusing error.

---

## Lesson 5 -- Memory is the durable layer; chat is the volatile one

### What happened

The same recurring failure modes (skipping skill invocation, treating non-blocking comments as ignorable, pinning bugs on external suspects without clean-room reproduction) showed up across multiple sessions. The fix was always re-stated in the moment ("don't do this", "always check that") and lost when the session ended.

When the system included file-based memory (durable, indexed, loaded into every session's context), each fix landed once and stuck. When fixes lived only in the session transcript, they decayed by the next conversation.

### What was wrong with the response

Important guidance was being delivered as in-chat instruction without ever being written to a memory file or to the project's `CLAUDE.md`. The instruction had zero half-life beyond the current session.

### What changed in the system

Every behaviour-shaping correction now follows a two-step ritual:

1. Save it as a memory file in the project's memory directory, with the right type tag (`feedback`, `project`, `reference`, `user`) and a one-line pointer in the index.
2. If the rule is durable enough to govern future sessions on the same project, also lift it into `CLAUDE.md` so it loads automatically regardless of memory state.

Memory files capture the *reason* and the *applicability conditions* (the `Why:` and `How to apply:` lines). `CLAUDE.md` captures the rule itself. The two layers reinforce each other: the rule is loud (always in context), the reasoning is reachable (one read away).

### Generalisable pattern

Instructions delivered only in chat are designed to be forgotten. If a correction is important enough to make twice, it is important enough to write down once. The first time you find yourself repeating the same guidance in a new session, that's the signal to move it to durable storage.

---

## How to use this document

Each lesson here is a real incident with a real rule change attached. The pattern at the bottom of each is the part that generalises beyond the original project.

When you encounter a new failure mode worth capturing, follow the same shape:

1. **What happened** -- the specific situation, not a paraphrase.
2. **What was wrong with the response** -- diagnose the *response*, not the underlying technical bug. The technical bug is solved by the technical fix; the response is what changes the system.
3. **What changed in the system** -- the exact rule added to your `CLAUDE.md` / memory / pipeline.
4. **Generalisable pattern** -- the one-paragraph version that explains why the rule exists, so future readers can apply it to situations that don't exactly match the original.

Append, don't overwrite. The accumulating list is the value.


---

## Lesson 6 -- Branch from fresh main; re-run flakes, don't chase them

### What happened

Two failure modes recurred across consecutive PRs on the same project.

First: a sequence of PRs touched overlapping code (`intake.py` and a shared `set_status` helper). The second branch was cut before the first merged, off a local `main` that was already behind. Every later PR in the chain hit avoidable merge conflicts — the same edits re-surfacing as "conflicts" against a `main` that had since moved.

Second: a required CI check went red with a wall of `ERROR`s. The failures were all at fixture setup on a single matrix leg — testcontainers couldn't bring up Docker on one Python version. The other legs were green and no assertion had actually failed. The reflex was to treat red-required-check as "my code is broken" and start editing to make it pass.

### What was wrong with the response

Both stem from skipping a cheap verification step before acting.

The stacked-conflict churn came from branching off stale/parallel state instead of off freshly-pulled `main` after the predecessor merged. The work was sequence-dependent and was treated as if it were independent.

The flake-chasing came from conflating "the check is red" with "my code is wrong." A check that errors at *setup* on *one leg* never ran the assertions — it carries no signal about the code. Editing code to chase it is debugging a phantom, and risks shipping a change that only "fixed" a green by coincidence.

### What changed in the system

Two rules landed in the branch & PR pipeline:

> Right before each new PR: `git checkout main && git pull`, then branch. When two PRs touch overlapping files, merge the first before branching the second — branching off pre-merge `main` guarantees stacked-conflict churn.

> A required check that mass-`ERROR`s at fixture/setup on a single matrix leg (Docker/testcontainers, one language version) is a flake, not your bug. Re-run the failed job. Distinguish "tests ran and asserted false" (your bug) from "tests never started" (infra flake) before touching code.

### Generalisable pattern

Before acting on git state or a CI signal, verify what the state/signal actually *is*. Stale `main` and a setup-phase flake both *look like* work to do — a conflict to resolve, a failure to fix — but the correct response is to refresh the base or re-run the job, not to start editing. The expensive mistakes here are mis-routed effort: solving a conflict that a fresh branch wouldn't have, or "fixing" code against a check that never tested it. One pull, one re-run, one `workspace show` — cheap checks that prevent hours of chasing the wrong thing.

---

## Lesson 7 -- Multi-agent is opt-in, and for parallel work not serial chains

### What happened

The multi-agent / Ultracode engine (the Workflow orchestrator) can spawn dozens of agents in one invocation. Two failure modes recurred: (a) it got reached for unprompted, on tasks where the user never asked for a workflow, burning large token budgets by default; and (b) it got pointed at sequential, gate-bound chains (cross-repo wiring, deploy-gated steps), where fanning out a serial pipeline added agent overhead without moving the actual bottleneck — every stage still had to wait on the verified output of the one before it, and the human/CI gates downstream were unchanged.

### What was wrong with the response

The engine was treated as a general accelerator ("more agents = faster"). It isn't. It is a tool for breadth and adversarial depth, not for compressing a dependency chain. Parallelism only buys speed when the units of work are independent. A serial chain run in parallel is still serial — you just pay for the orchestration. And reaching for it without being asked imports a token cost the user never signed up for, often inferring a scale ("audit everything") the user never specified.

### What changed in the system

A "Multi-agent / Ultracode usage" section was added to global guidance with three gates:

> 1. **Opt-in only.** Invoke the engine only on the keyword `ultracode`, an explicit "use a workflow / fan out agents" request, or a skill that calls it. Never infer scale the user did not ask for.
> 2. **Fit-for-parallel, not serial.** Good fits are parallel/broad/adversarial/scale: review councils, adversarial audits with refuting skeptics + majority vote, completeness sweeps, broad migrations. Bad fits are sequential, gate-bound, judgment-heavy chains — keep those single-threaded. For light cases, a few plain subagents you synthesize beat the full engine; reserve the engine for exhaustive/looping passes.
> 3. **Cost honesty.** When a workflow bounds coverage (top-N, sampling, no-retry), state what was dropped.

### Generalisable pattern

Parallelism is a property of the *work*, not a speed dial. Independent breadth and adversarial depth parallelize; dependency chains do not. Before fanning out, ask "are these units actually independent?" and "did the user ask for this scale?" — if either answer is no, stay single-threaded and say what you're not covering.

---

## Lesson 8 -- Convene a skill council for load-bearing design; ground the names before you build

### What happened

A design question -- how should "cards" and "workspaces" be modelled so they are shareable and reusable -- started with the assistant answering each new scenario by adding a *type* or an *enum value*: a per-account card, then a `scope: global` card, then a `scope: cohort` card. The operator caught it: *"every new case creates a new type -- the architecture is not sustainable. Challenge how cards are built."*

Instead of patching further, the work was restructured as a sequence of domain-expert skills, each refining the last: `senior-data-scientist` (aggregation correctness) -> `product-manager` (shareability scope) -> `architecture-patterns` (the Open/Closed restructure) -> `ddd-strategic-design` (bounded contexts, ubiquitous language) -> `ddd-tactical-patterns` (aggregate / value-object / specification). Before any of it was written to an ADR, the proposed vocabulary was checked against two *external* jargons -- DDD and dimensional / semantic-layer (OLAP) modelling -- which surfaced that "Measure" should be "Metric", that "Reducer" was FP jargon hiding the **additivity** hazard, and that "Population" had silently fused *selection* with *grain*.

### What was wrong with the response

The first instinct -- one skill, one pass, a new type per case -- produced a combinatorial type explosion (cardinality x time-mode x presentation) and named the concepts in ad-hoc language. A single domain lens cannot catch a cross-domain modelling error: the data-science lens sees the aggregation trap, the DDD lens sees the value-object / aggregate boundary, the dimensional-modelling lens sees the grain / measure confusion. Answering from one seat misses the others.

### What changed in the system

A rule for load-bearing design decisions (schema, domain model, anything that becomes an ADR):

> Do not one-shot a structural design from a single skill. Convene a **council**: invoke domain skills in sequence, each consuming the prior's output (DS -> PM -> architecture -> DDD strategic -> DDD tactical is a strong default for a data-modelling decision). Before codifying the result, **validate the nomenclature against the established jargon of the relevant fields** -- the right word usually already exists and often carries a known hazard in its name (e.g. *non-additive measure* warns you not to average it). Variation that recurs as "a new type per case" belongs in **data (config), not types (code)**; treat new-type-per-scenario as a modelling smell to challenge.

### Generalisable pattern

A council of narrow experts beats one generalist pass on any decision that spans domains -- and almost every structural decision does. The sequence matters (each lens refines the last), and the cheapest quality gate is *naming*: map your invented terms onto the field's existing vocabulary before you write them into a schema or ADR. If a single skill keeps adding types to cover new cases, stop and ask whether the variation is data.

---

## Lesson 9 -- Long-running tasks survive a shared working directory only if you drive them remotely

### What happened

Several Claude Code sessions shared one working directory. Midway through a multi-PR task (open a PR, address bot review, merge, then a follow-up fix PR), a *concurrent* session switched the shared checkout back to `main` -- the local branch changed under an in-flight task. Commits were not lost (they were already pushed), but any further step that assumed "I am on branch X locally" would have acted on the wrong tree.

### What was wrong with the response

The task had been planned around local git state (checkout the branch, rebase, push). In a shared working directory that assumption is unsafe: another session's `git checkout` mutates your ground. Relying on local branch position for a long-running, interrupt-prone task is a race.

### What changed in the system

Two habits for long-running VCS tasks in shared working-tree environments:

> 1. Drive through **remote** operations that do not depend on the local checkout: `gh pr merge`, `gh pr update-branch`, `gh api` -- not `git checkout` + local rebase -- whenever a remote equivalent exists. The PR, not the working tree, is the unit of state.
> 2. **Inline per-command credentials** (`GH_TOKEN=$(...) gh ...`) so a global `gh auth switch` by you or another session never silently retargets your writes. Re-fetch state (`gh pr view`) at the start of every resumed step rather than trusting remembered position.

### Generalisable pattern

A working directory is shared mutable state. Any task that spans multiple turns or sleeps on CI can be interrupted by another actor editing that state. Keep the durable unit of work somewhere the interruption cannot move it -- here, the remote PR -- and re-read state on resume instead of trusting what you remember. This is the working-tree analogue of Lesson 4's identity hygiene.

---

## Lesson 10 -- A documented merge process is not an enforced one

### What happened

A project ran an elaborate PR pipeline in its `CLAUDE.md` -- mandatory reviews, required green checks, a response gate -- for months. While setting up branch protection, a one-line API check revealed `main` was **not protected at all**: zero required status checks, direct pushes allowed, no gate. The entire documented process was convention, enforced only by the operator and assistant remembering to follow it.

### What was wrong with the response

The process doc had been treated as if writing the rule enforced it. Nothing in the substrate (GitHub branch protection / rulesets) backed the policy. A single direct push, or one forgotten check, would bypass the whole pipeline with no friction.

### What changed in the system

Branch protection was made to match the *actual* review topology, with two design rules that are easy to get wrong:

> 1. **Require only checks that run on every PR.** A path-filtered check (one that only fires on certain directories) marked as required will hang a PR forever as "expected -- waiting", because it never reports on PRs that do not touch its paths. Require the always-run subset; verify each required context name matches the live check name exactly.
> 2. **Match the gate to who actually reviews.** Bot reviewers (Gemini, Claude auto-review) *comment*; they do not `APPROVE`. Requiring a human approving review when the author is usually solo self-blocks every PR. For a solo + bots topology, gate on **CI + PR-required**, not human approval, and let the bots gate via their own check.

And a standing check: when a process doc assumes an enforcement substrate (branch protection, required checks, CODEOWNERS), verify the substrate exists -- do not assume the written rule is live.

### Generalisable pattern

Documentation describes intent; it does not enforce it. Any policy that *could* be enforced by the platform but is not is one slip from being bypassed silently. Periodically reconcile the written process against the actual configuration, and when you wire the enforcement, shape it to your real review topology -- the wrong required check (path-filtered, or a human approval a solo author cannot give) converts "protected" into "permanently blocked".
