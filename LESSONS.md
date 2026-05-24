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
