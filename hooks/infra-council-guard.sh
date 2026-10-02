#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash) -- blocks an infrastructure MUTATION unless a
# multi-agent council review exists in the repo, is committed, comes AFTER the
# infra change it reviews, and passes agent-council-lint.py.
#
# The council verdict is not a conversation, it is an ARTIFACT in the
# development graph -- committed, reviewable, and attached to the change it
# approved (templates/global.md, Infra Council Gate).
#
# Why a hook and not a note in CLAUDE.md: Lesson 17 -- a lesson that is not a
# gate gets re-violated. Prose does not execute.
#
# Why "after" rather than "exists": a council record that predates the infra it
# approves reviewed something else -- the same failure as a monitoring check whose
# lastCheck precedes its data. "After" is ANCESTRY (the newest infra commit must be
# an ancestor of the record's commit), not commit dates, which are forgeable.
#
# Why the lint: a record that exists and is fresh but spans one model family, puts
# the refuter on the author's family, or records no real dissent reviewed nothing
# the author did not already believe (LESSONS Lesson 30).
#
# READ-ONLY commands are never blocked: plan, validate, fmt, init, show, preview,
# state list, output, and read-only AWS calls (describe/list/get/ls). Only mutations.
#
# Configuration (environment, all optional):
#   INFRA_COUNCIL_PATHS  space-separated git pathspecs that are infrastructure
#                        (default below; add your cdk/pulumi program directories)
#   INFRA_COUNCIL_DIR    council record directory, relative to the repo root
#                        (default: docs/council)
#   INFRA_COUNCIL_LINT   path to agent-council-lint.py (default: next to this hook),
#                        or "off" to skip the record lint. A missing linter blocks.
#   INFRA_COUNCIL_PYTHON interpreter for the lint (default: the first python3 on PATH
#                        that can import PyYAML). None found blocks. The lint's verdict is
#                        only as trustworthy as this interpreter: pin an absolute path in
#                        the hook's environment if PATH is not yours.
#
# Limits: this reads the command TEXT. It over-blocks (a mutation named in a string
# or heredoc is blocked; run such scripts from a file) and it cannot see through
# indirection: a variable holding the command, a wrapper script, `make deploy`, an
# alias. It is a guard against the agent's own direct commands, not a sandbox.
#
# Fails closed: any unexpected error exits 2, Claude Code's blocking exit for a
# PreToolUse hook, which needs no jq.
#
# Register in ~/.claude/settings.json under PreToolUse with matcher "Bash".

set -Eeuo pipefail
trap 'echo "infra-council-guard: internal error at line $LINENO; blocking (fix the hook or its environment)." >&2; exit 2' ERR

# grep, awk, sed and tr matter as much as jq: one missing inside an `if` reads as
# "no mutation" and would allow everything.
for tool in jq git grep awk sed tr; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "infra-council-guard: $tool not found on PATH; blocking every Bash call until it is installed." >&2
        exit 2
    }
done

INPUT=$(cat)
TOOL=$(jq -r '.tool_name // ""' <<<"$INPUT")
[ "$TOOL" = "Bash" ] || exit 0
CMD=$(jq -r '.tool_input.command // ""' <<<"$INPUT")
HOOK_CWD=$(jq -r '.cwd // ""' <<<"$INPUT")
[ -n "$HOOK_CWD" ] || HOOK_CWD="$PWD"

block() {
    jq -cn --arg r "$1" '{decision:"block", reason:$r, hookSpecificOutput:{hookEventName:"PreToolUse", permissionDecision:"deny", permissionDecisionReason:$r}}'
    exit 0
}

# Read as the shell will run it: line continuations joined, quotes dropped, so
# `terraform \<newline>apply` and `terraform 'apply'` match.
NORM=$(printf '%s\n' "$CMD" | awk '{ if (sub(/\\$/, "")) printf "%s ", $0; else print }' | tr -d "\"'")

# ---------------------------------------------------------------------------
# 1. What does the command mutate?
# ---------------------------------------------------------------------------
# Global flags, each optionally followed by one value, between a binary and its
# subcommand: `terraform -chdir=infra apply`, `pulumi --stack prod up`.
OPTS='([[:space:]]+-[^[:space:]]+([[:space:]]+[^-[:space:]][^[:space:]]*)?)*[[:space:]]+'
MUTATE_RE="(^|[^[:alnum:]_-])(terraform|tofu)${OPTS}(apply|destroy|import|taint|untaint|refresh|force-unlock)([[:space:]]|$)"
MUTATE_RE="$MUTATE_RE|(^|[^[:alnum:]_-])(terraform|tofu)${OPTS}(state${OPTS}(rm|mv|push|replace-provider)|workspace${OPTS}delete)([[:space:]]|$)"
MUTATE_RE="$MUTATE_RE|(^|[^[:alnum:]_-])terragrunt([[:space:]][^;&|]*)?[[:space:]](apply|destroy|import)([[:space:]]|$)"
MUTATE_RE="$MUTATE_RE|(^|[^[:alnum:]_-])pulumi${OPTS}(up|destroy|refresh|import)([[:space:]]|$)"
MUTATE_RE="$MUTATE_RE|(^|[^[:alnum:]_-])cdk${OPTS}(deploy|destroy)([[:space:]]|$)"
MUTATE_RE="$MUTATE_RE|(^|[^[:alnum:]_-])(serverless|sls)${OPTS}(deploy|remove)([[:space:]]|$)"
MUTATE_RE="$MUTATE_RE|(^|[^[:alnum:]_-])sam${OPTS}(deploy|delete)([[:space:]]|$)"
MUTATE_RE="$MUTATE_RE|(^|[^[:alnum:]_-])aws${OPTS}cloudformation${OPTS}(create-stack|update-stack|delete-stack|deploy|execute-change-set)([[:space:]]|$)"
IAC=0
if printf '%s\n' "$NORM" | grep -qE "$MUTATE_RE"; then IAC=1; fi

# Raw AWS control-plane mutations, judged one shell segment at a time: a segment is
# a mutation if any of its <verb>-<noun> tokens has a config-mutating verb that is not
# one of the operational calls. An operational call in one segment excuses nothing in
# another, and `--description put-events` cannot launder `create-role`.
AWS_VERBS='create|update|put|delete|modify|attach|detach|associate|disassociate|add|remove|replace|tag|untag|enable|disable|register|deregister|set|import|apply|restore|rotate|reset|revoke|authorize|terminate|reboot'
# run-/start-/stop-/cancel-/schedule- are mostly RUNTIME (run-task, start-query,
# start-execution, stop-task) and stay open; these named ones change infrastructure.
AWS_CONTROL='run-instances|start-instances|stop-instances|schedule-key-deletion|cancel-key-deletion|start-db-instance|stop-db-instance|start-db-cluster|stop-db-cluster'
AWS_OPS='set-alarm-state|put-metric-data|put-log-events|put-events'
AWS_SEG_RE='(^|[[:space:](/])aws[[:space:]]'
RAW_AWS=0
while IFS= read -r seg; do
    printf '%s\n' "$seg" | grep -qE "$AWS_SEG_RE" || continue
    if printf '%s\n' "$seg" | grep -qE "[[:space:]]s3[[:space:]]+(rb|rm|mv|sync)([[:space:]]|$)"; then
        RAW_AWS=1
        break
    fi
    VERB_TOKENS=$(printf '%s\n' "$seg" | tr -s '[:space:]' '\n' | grep -E "^((${AWS_VERBS})-[a-z0-9-]+|${AWS_CONTROL})$" || true)
    if [ -n "$VERB_TOKENS" ] && printf '%s\n' "$VERB_TOKENS" | grep -qvxE "$AWS_OPS"; then
        RAW_AWS=1
        break
    fi
done < <(printf '%s\n' "$NORM" | tr ';&|' '\n\n\n')

if [ "$IAC" = 0 ] && [ "$RAW_AWS" = 0 ]; then exit 0; fi

# ---------------------------------------------------------------------------
# 2. Configuration and the repository the session is in
# ---------------------------------------------------------------------------
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PATHS='infra/ *.tf *.tfvars *.tf.json *.hcl serverless.yml serverless.yaml template.yaml template.yml samconfig.toml cdk.json Pulumi.yaml Pulumi.*.yaml'
INFRA_PATHS=()
read -r -a INFRA_PATHS <<<"${INFRA_COUNCIL_PATHS-$DEFAULT_PATHS}" || true
if [ -z "${INFRA_PATHS[*]:-}" ]; then
    block "Infrastructure mutation BLOCKED -- INFRA_COUNCIL_PATHS is set but empty, so nothing would count as infrastructure. Unset it for the default, or list the pathspecs."
fi
COUNCIL_REL="${INFRA_COUNCIL_DIR:-docs/council}"
COUNCIL_REL="${COUNCIL_REL%/}"
case "$COUNCIL_REL" in
    "" | . | ./* | /* | .. | ../* | */.. | */../*)
        block "Infrastructure mutation BLOCKED -- INFRA_COUNCIL_DIR must be a directory inside the repo, relative to its root and without '..' or '.'; got '${INFRA_COUNCIL_DIR:-}'."
        ;;
esac
LINT="${INFRA_COUNCIL_LINT:-$HOOK_DIR/agent-council-lint.py}"

REPO=$(git -C "$HOOK_CWD" rev-parse --show-toplevel 2>/dev/null || echo "")
if [ -z "$REPO" ]; then
    block 'Infrastructure mutation BLOCKED: not inside a git repository.

An infra change that is not in version control cannot be reviewed, cannot be
rolled back, and leaves no record of what was deployed or why. Run this from the
repository that owns the infrastructure.'
fi
REPO=$(cd "$REPO" && pwd -P)
if [ "$(git -C "$REPO" rev-parse --is-shallow-repository)" != false ]; then
    block "Infrastructure mutation BLOCKED -- $REPO is a shallow clone: the history that decides whether the council record comes after the infra change is missing. Fetch full history (git fetch --unshallow) and re-run."
fi

# The newest commit touching the infra paths.
INFRA_COMMIT=$(git -C "$REPO" log -1 --topo-order --format=%H -- "${INFRA_PATHS[@]}" 2>/dev/null || true)

# Records eligible to be "the council record": *.md under the council dir, not a
# README.md, and with no path component starting with "_" (templates, drafts).
is_record() {
    case "$1" in *.md) ;; *) return 1 ;; esac
    if printf '%s\n' "$1" | grep -qE '(^|/)(README[.]md$|_)'; then return 1; fi
    return 0
}

# The interpreter for the lint: INFRA_COUNCIL_PYTHON if set, else the first python3 on
# PATH that can import PyYAML (a project venv often shadows the one that has it).
# Prints the interpreter, or nothing. Probes read /dev/null: a candidate that reads
# stdin would otherwise swallow the remaining candidates.
lint_python() {
    local candidate
    if [ -n "${INFRA_COUNCIL_PYTHON:-}" ]; then
        if "$INFRA_COUNCIL_PYTHON" -c 'import yaml' </dev/null >/dev/null 2>&1; then
            printf '%s' "$INFRA_COUNCIL_PYTHON"
        fi
        return 0
    fi
    while IFS= read -r candidate; do
        [ -n "$candidate" ] || continue
        if "$candidate" -c 'import yaml' </dev/null >/dev/null 2>&1; then
            printf '%s' "$candidate"
            return 0
        fi
    done < <(type -a -p python3 2>/dev/null || true)
    return 0
}

# Prints why `rel` is not a usable committed record for this infra state, or nothing.
record_reason() {
    local rel="$1" rec_commit="$2" mode tmp out rc=0
    mode=$(git -C "$REPO" ls-tree HEAD -- "$rel" | awk '{print $1}')
    if [ "$mode" = 120000 ]; then
        printf 'Council record %s is a symlink. The record must be a committed file, not a pointer to something editable outside the graph.' "$rel"
        return 0
    fi
    if [ -n "$INFRA_COMMIT" ] && ! git -C "$REPO" merge-base --is-ancestor "$INFRA_COMMIT" "$rec_commit" 2>/dev/null; then
        printf 'Council record %s PRE-DATES the newest infra commit (%s): it reviewed something else.' "$rel" "${INFRA_COMMIT:0:12}"
        return 0
    fi
    if [ "$LINT" = off ]; then return 0; fi
    if [ ! -f "$LINT" ]; then
        printf 'agent-council-lint.py not found at %s. Install it next to this hook, point INFRA_COUNCIL_LINT at it, or set INFRA_COUNCIL_LINT=off.' "$LINT"
        return 0
    fi
    local py
    py=$(lint_python)
    if [ -z "$py" ]; then
        printf 'No python3 with PyYAML found for agent-council-lint.py (tried %s). Install PyYAML for one of them, or set INFRA_COUNCIL_PYTHON.' "${INFRA_COUNCIL_PYTHON:-every python3 on PATH}"
        return 0
    fi
    # Lint the COMMITTED blob, under its own file name (the date in the name is a rule).
    tmp=$(mktemp -d)
    git -C "$REPO" show "HEAD:$rel" >"$tmp/$(basename "$rel")"
    out=$("$py" "$LINT" --council "$tmp/$(basename "$rel")" 2>&1) || rc=$?
    rm -rf "$tmp"
    if [ "$rc" -eq 0 ]; then return 0; fi
    printf 'Council record %s fails agent-council-lint (exit %s):\n%s' "$rel" "$rc" "$(printf '%s\n' "$out" | sed -n '1,20p')"
}

# ---------------------------------------------------------------------------
# 3. Raw AWS mutation: needs COUNCIL_ACK=<record> in THIS repository
# ---------------------------------------------------------------------------
if [ "$RAW_AWS" = 1 ]; then
    ACK=$(printf '%s\n' "$CMD" | grep -oE 'COUNCIL_ACK=[^[:space:];&|]+' | head -1 | cut -d= -f2- || true)
    ACK_REASON="No COUNCIL_ACK given."
    if [ -n "$ACK" ]; then
        case "$ACK" in /*) ACK_PATH="$ACK" ;; *) ACK_PATH="$HOOK_CWD/$ACK" ;; esac
        ACK_DIR=$(cd "$(dirname "$ACK_PATH")" 2>/dev/null && pwd -P || echo "")
        ACK_REPO=""
        if [ -n "$ACK_DIR" ]; then
            ACK_REPO=$(git -C "$ACK_DIR" rev-parse --show-toplevel 2>/dev/null || echo "")
        fi
        if [ -n "$ACK_REPO" ]; then ACK_REPO=$(cd "$ACK_REPO" && pwd -P); fi
        ACK_REL="${ACK_DIR#"$REPO"/}/$(basename "$ACK_PATH")"
        if [ -z "$ACK_REPO" ] || [ ! -f "$ACK_PATH" ]; then
            ACK_REASON="COUNCIL_ACK names $ACK, which is not a file inside a git repository."
        elif [ "$ACK_REPO" != "$REPO" ]; then
            ACK_REASON="COUNCIL_ACK names a record in $ACK_REPO; it must be in the same repository as the session ($REPO)."
        elif [ "${ACK_REL#"$COUNCIL_REL"/}" = "$ACK_REL" ] || ! is_record "${ACK_REL#"$COUNCIL_REL"/}"; then
            ACK_REASON="COUNCIL_ACK must name a $COUNCIL_REL/*.md record (not a README.md or _template); got $ACK_REL."
        else
            ACK_COMMIT=$(git -C "$REPO" log -1 --format=%H -- "$ACK_REL" 2>/dev/null || true)
            if [ -z "$ACK_COMMIT" ]; then
                ACK_REASON="COUNCIL_ACK names $ACK_REL, which is not committed. An uncommitted record is not in the graph."
            elif ! git -C "$REPO" diff --quiet HEAD -- "$ACK_REL" 2>/dev/null; then
                ACK_REASON="COUNCIL_ACK names $ACK_REL, which has uncommitted edits. The committed version is the record."
            else
                ACK_REASON=$(record_reason "$ACK_REL" "$ACK_COMMIT")
                ACK_REASON=${ACK_REASON/PRE-DATES the newest infra commit/PRE-DATES the newest infra commit in $REPO}
            fi
        fi
    fi
    if [ -n "$ACK_REASON" ]; then
        block "$(printf 'Raw AWS infrastructure mutation BLOCKED.

Command: %s

%s

A direct API mutation bypasses IaC and the council: it creates drift no plan
was reviewed for, and leaves no record in the development graph.

TO PROCEED, either:
  1. Make the change in the IaC that owns the resource, with a council record
     (see the IaC gate), or
  2. If a committed council record already authorises this exact operation
     (a probe, a secret seed, a recovery step), prefix the command with
       COUNCIL_ACK=<council dir>/<file>.md   (default dir: docs/council)
     The record must be committed, in this repository, come after the newest
     infra commit, and pass agent-council-lint.py.

Read-only AWS calls (describe/list/get/ls) and operational writes
(set-alarm-state, put-metric-data, put-log-events, put-events) are never blocked.' "$CMD" "$ACK_REASON")"
    fi
    # The ACK covers the raw AWS call only. An IaC mutation in the same command still
    # has to pass the IaC gate below.
    if [ "$IAC" = 0 ]; then exit 0; fi
fi

# ---------------------------------------------------------------------------
# 4. IaC mutation: the command must act on this repository
# ---------------------------------------------------------------------------
OUTSIDE=""
while IFS= read -r dir; do
    [ -n "$dir" ] || continue
    # shellcheck disable=SC2088  # matching a literal "~" the shell has not expanded
    case "$dir" in "~" | "~/"*) dir="$HOME${dir#\~}" ;; esac
    case "$dir" in /*) ;; *) dir="$HOOK_CWD/$dir" ;; esac
    resolved=$(cd "$dir" 2>/dev/null && pwd -P || echo "")
    case "$resolved/" in
        "$REPO"/*) ;;
        *)
            OUTSIDE="$dir"
            break
            ;;
    esac
done < <(printf '%s\n' "$NORM" | grep -oE '(^|[;&|[:space:](])(cd|pushd)[[:space:]]+[^;&|[:space:])]+|-chdir=[^;&|[:space:]]+|git[[:space:]]+-C[[:space:]]+[^;&|[:space:]]+' |
    sed -E 's/^[;&|[:space:](]*(cd|pushd)[[:space:]]+//; s/^-chdir=//; s/^git[[:space:]]+-C[[:space:]]+//' || true)
if [ -n "$OUTSIDE" ]; then
    block "Infrastructure mutation BLOCKED -- the command moves to $OUTSIDE, outside the session repository ($REPO). The council gate only knows about the repository the session is in; run the command from the repository that owns that infrastructure."
fi

# ---------------------------------------------------------------------------
# 5. Clean tree, a record, after the infra, linted
# ---------------------------------------------------------------------------
# UNCOMMITTED infra changes are newer than any council, always: the record reviews
# what is committed, and an apply applies the working tree.
DIRTY_ALL=$(git -C "$REPO" status --porcelain -- "${INFRA_PATHS[@]}" 2>/dev/null || true)
if [ -n "$DIRTY_ALL" ]; then
    DIRTY=$(printf '%s\n' "$DIRTY_ALL" | sed -n '1,20p')
    block "$(printf 'Infrastructure mutation BLOCKED -- uncommitted changes under the infra paths (%s).

%s

The council record reviews what is COMMITTED, so an apply from a dirty working tree
applies something no council has seen -- however fresh the record looks. Commit the
infra change together with the council record that covers it, then re-run.' "${INFRA_PATHS[*]}" "$DIRTY")"
fi

# The newest commit that added or modified a record that still exists. Every record
# that commit touched is checked: one bad record cannot hide behind a good one.
RECORD_COMMIT=""
RECORDS=()
while IFS= read -r commit; do
    found=()
    while IFS= read -r rel; do
        [ -n "$rel" ] || continue
        is_record "${rel#"$COUNCIL_REL"/}" || continue
        git -C "$REPO" cat-file -e "HEAD:$rel" 2>/dev/null || continue
        found+=("$rel")
    done < <(git -C "$REPO" diff-tree --no-commit-id --name-only -r --root --diff-filter=AM "$commit" -- "$COUNCIL_REL/" 2>/dev/null || true)
    if [ -n "${found[*]:-}" ]; then
        RECORD_COMMIT="$commit"
        RECORDS=("${found[@]}")
        break
    fi
done < <(git -C "$REPO" log --topo-order --format=%H -- "$COUNCIL_REL/" 2>/dev/null || true)

if [ -z "$RECORD_COMMIT" ]; then
    block "$(printf 'Infrastructure mutation BLOCKED -- no council review in the development graph.

Command: %s

No council record exists in %s/ (a *.md other than README.md or _templates).

No infra deployment goes through without a council review recorded as an
artifact, not held in a conversation.

TO SATISFY THIS GATE:
  1. Run a multi-agent council over the pending change. Minimum four lenses,
     each an independent agent, none of them the author:
       - reliability / observability   (what failure is NOT alarmed?)
       - security / IAM blast radius   (least privilege, secret paths, state)
       - IaC architecture & delivery   (drift, reproducibility, CI vs local)
       - cost / operational burden     (right-sizing, recurring toil)
  2. Write the verdict to %s/<YYYY-MM-DD>-<topic>.md in the frontmatter format
     agent-council-lint.py checks: lenses with their models across two model
     families, a refuter on a different family from the author, and real
     DISAGREEMENTS and REJECTED sections -- a record with no dissent is a
     rubber stamp.
  3. COMMIT it, after the infra change it reviews.
  4. Re-run this command.

Read-only work is never blocked: plan / validate / fmt / init / show / preview,
and every read-only AWS call.' "$CMD" "$COUNCIL_REL" "$COUNCIL_REL")"
fi

for rel in "${RECORDS[@]}"; do
    REASON=$(record_reason "$rel" "$RECORD_COMMIT")
    if [ -n "$REASON" ]; then
        block "$(printf 'Infrastructure mutation BLOCKED -- the newest council record does not clear the gate.

%s

Older records are not considered: the newest one is the review of the current
change. Fix or add a record, commit it after the infra change, and re-run.' "$REASON")"
    fi
done
exit 0
