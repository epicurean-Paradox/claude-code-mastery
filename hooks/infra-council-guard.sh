#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash) -- blocks an infrastructure MUTATION unless a
# multi-agent council review exists in the repo AND post-dates the infra change
# it is supposed to have reviewed.
#
# The council verdict is not a conversation, it is an ARTIFACT in the
# development graph -- committed, reviewable, and attached to the change it
# approved (templates/global.md, Infra Council Gate).
#
# Why a hook and not a note in CLAUDE.md: Lesson 17 -- a lesson that is not a
# gate gets re-violated. Prose does not execute.
#
# Why "post-dates" rather than "exists": a council file that predates the infra
# it approves reviewed something else. That is the same stale-verdict failure as
# a monitoring check whose lastCheck precedes its data. The freshness comparison
# is the core of the gate.
#
# READ-ONLY infra commands are never blocked: plan, validate, fmt, init, show,
# state list, output, and every read-only AWS call. Only mutations gate.
#
# Register in ~/.claude/settings.json under PreToolUse with matcher "Bash".

set -euo pipefail

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""')
[ "$TOOL" = "Bash" ] || exit 0

CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""')
HOOK_CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // ""')

block() {
    jq -cn --arg r "$1" '{decision:"block", reason:$r, hookSpecificOutput:{hookEventName:"PreToolUse", permissionDecision:"deny", permissionDecisionReason:$r}}'
    exit 0
}

# ---------------------------------------------------------------------------
# 0. Raw AWS control-plane mutations
# ---------------------------------------------------------------------------
# The IaC match below never saw `aws budgets update-budget`: an agent session
# once rewrote a production budget straight through the API, outside Terraform
# and before any council.
#
# Match: an `aws` invocation whose subcommand token is <verb>-<noun> with a
# config-mutating verb, inside one shell segment (no crossing | ; &). Read verbs
# (describe/list/get/lookup/search) and runtime verbs (run-task, invoke, send-*,
# start-query) never match, so verification stays ungated.
AWS_VERBS='create|update|put|delete|modify|attach|detach|associate|disassociate|add|remove|replace|tag|untag|enable|disable|register|deregister|set|import|apply|restore|rotate|reset|revoke|authorize|terminate|reboot'
AWS_MUT_RE='(^|[;&|[:space:](])aws[[:space:]][^|;&]*[[:space:]]('"$AWS_VERBS"')-[a-z0-9-]+([[:space:]]|$)'
# Operational writes that change no infrastructure config.
AWS_OPS_RE='[[:space:]](set-alarm-state|put-metric-data|put-log-events|put-events)([[:space:]]|$)'

if printf '%s\n' "$CMD" | grep -qE "$AWS_MUT_RE"; then
    MUT_CMDS=$(printf '%s\n' "$CMD" | grep -oE "$AWS_MUT_RE" || true)
    if ! printf '%s\n' "$MUT_CMDS" | grep -vE "$AWS_OPS_RE" | grep -qE "aws[[:space:]]"; then
        exit 0  # every matched aws call is operational
    fi

    # PASS only by naming a COMMITTED council record that is not older than the
    # newest infra commit in its repo: COUNCIL_ACK=<path>/docs/council/<file>.md
    ACK=$(printf '%s\n' "$CMD" | grep -oE 'COUNCIL_ACK=[^[:space:];&|]+' | head -1 | cut -d= -f2- || true)
    ACK_REASON=""
    if [ -n "$ACK" ]; then
        case "$ACK" in /*) ACK_PATH="$ACK" ;; *) ACK_PATH="${HOOK_CWD:-$PWD}/$ACK" ;; esac
        # Physical path: git reports /private/tmp where the caller may say /tmp.
        ACK_DIR=$(cd "$(dirname "$ACK_PATH")" 2>/dev/null && pwd -P || echo "")
        ACK_PATH="$ACK_DIR/$(basename "$ACK_PATH")"
        ACK_REPO=$(git -C "$ACK_DIR" rev-parse --show-toplevel 2>/dev/null || echo "")
        ACK_REL=${ACK_PATH#"$ACK_REPO"/}
        if [ -z "$ACK_REPO" ] || [ ! -f "$ACK_PATH" ]; then
            ACK_REASON="COUNCIL_ACK names $ACK, which is not a file inside a git repository."
        elif [ "${ACK_REL#docs/council/}" = "$ACK_REL" ] || [ "${ACK_REL%.md}" = "$ACK_REL" ]; then
            ACK_REASON="COUNCIL_ACK must name a docs/council/*.md record; got $ACK_REL."
        else
            REC_TS=$(git -C "$ACK_REPO" log -1 --format=%ct -- "$ACK_REL" 2>/dev/null || true)
            REC_TS=${REC_TS:-0}
            NEWEST_INFRA=$(git -C "$ACK_REPO" log -1 --format=%ct -- infra/ '*.tf' 2>/dev/null || true)
            NEWEST_INFRA=${NEWEST_INFRA:-0}
            if [ "$REC_TS" -eq 0 ]; then
                ACK_REASON="COUNCIL_ACK names $ACK_REL, which is not committed. An uncommitted record is not in the graph."
            elif ! git -C "$ACK_REPO" diff --quiet HEAD -- "$ACK_REL" 2>/dev/null; then
                ACK_REASON="COUNCIL_ACK names $ACK_REL, which has uncommitted edits. The committed version is the record."
            elif [ "$REC_TS" -lt "$NEWEST_INFRA" ]; then
                ACK_REASON="COUNCIL_ACK names $ACK_REL, which PRE-DATES the newest infra commit in $ACK_REPO. It reviewed something else."
            else
                exit 0
            fi
        fi
    fi

    block "$(printf 'Raw AWS infrastructure mutation BLOCKED.

Command: %s

%s

A direct API mutation bypasses IaC and the council: it creates drift no plan
was reviewed for, and leaves no record in the development graph.

TO PROCEED, either:
  1. Make the change in the IaC that owns the resource, with a council record
     (see the terraform gate below), or
  2. If a committed council record already authorises this exact operation
     (a probe, a secret seed, a recovery step), prefix the command with
       COUNCIL_ACK=<repo>/docs/council/<file>.md
     The record must be committed and not older than the newest infra commit.

Read-only AWS calls (describe/list/get/lookup) and runtime calls (run-task,
invoke, send-*, set-alarm-state, put-metric-data) are never blocked.' "$CMD" "${ACK_REASON:-No COUNCIL_ACK given.}")"
fi

# ---------------------------------------------------------------------------
# 1. Is this an infrastructure MUTATION?
# ---------------------------------------------------------------------------
# Deliberately narrow on TOOLS -- a broad "any aws command" match would fire on
# the read-only verification this workflow depends on, and a gate that blocks
# verification trains people to disable it.
#
# But deliberately BROAD on the gap between the binary and its subcommand.
# Terraform takes global options before the subcommand, so `terraform apply` and
# `terraform -chdir=infra apply` are the same operation -- and an earlier version
# of this hook matched only the first, which meant the form actually used to
# deploy this stack sailed straight through. A gate that recognises one spelling
# of the command it guards is not a gate. `(-[^[:space:]]+[[:space:]]+)*` is the
# fix: any run of global flags between the binary and the subcommand.
OPTS='([[:space:]]+-[^[:space:]]+)*[[:space:]]+'
MUTATE_RE="(terraform|tofu)${OPTS}(apply|destroy|import|taint)"
MUTATE_RE="$MUTATE_RE"'|(terraform|tofu)'"${OPTS}"'state'"${OPTS}"'(rm|mv|push|replace-provider)'
MUTATE_RE="$MUTATE_RE"'|pulumi'"${OPTS}"'(up|destroy|refresh)'
MUTATE_RE="$MUTATE_RE"'|cdk'"${OPTS}"'(deploy|destroy)'
MUTATE_RE="$MUTATE_RE"'|(serverless|sls)'"${OPTS}"'(deploy|remove)'
MUTATE_RE="$MUTATE_RE"'|sam'"${OPTS}"'deploy'
MUTATE_RE="$MUTATE_RE"'|aws'"${OPTS}"'cloudformation'"${OPTS}"'(create-stack|update-stack|delete-stack|deploy|execute-change-set)'

printf '%s\n' "$CMD" | grep -qE "$MUTATE_RE" || exit 0

# No exemption clause. An earlier version tried to let a command through when it
# ALSO mentioned a read-only subcommand, which meant `terraform plan && terraform
# apply` -- the single most natural way to run this -- was exempted by its own
# first half. Read-only commands simply never match MUTATE_RE in the first place;
# they need no escape hatch, and every escape hatch here is a bypass.

# ---------------------------------------------------------------------------
# 2. Locate the repo and look for a council record that post-dates infra/
# ---------------------------------------------------------------------------
REPO=$(git rev-parse --show-toplevel 2>/dev/null || echo "")

if [ -z "$REPO" ]; then
    REASON='Infrastructure mutation BLOCKED: not inside a git repository.

An infra change that is not in version control cannot be reviewed, cannot be
rolled back, and leaves no record of what was deployed or why. Run this from the
repository that owns the infrastructure.'
    jq -cn --arg r "$REASON" '{decision:"block", reason:$r, hookSpecificOutput:{hookEventName:"PreToolUse", permissionDecision:"deny", permissionDecisionReason:$r}}'
    exit 0
fi

COUNCIL_DIR="$REPO/docs/council"

# Newest commit touching infrastructure, and newest touching the council record.
# Committed timestamps, not file mtimes: mtime is trivially satisfied by `touch`
# and says nothing about what entered the development graph.
INFRA_TS=$(cd "$REPO" && git log -1 --format=%ct -- infra/ '*.tf' 2>/dev/null || echo 0)
INFRA_TS=${INFRA_TS:-0}
COUNCIL_TS=$(cd "$REPO" && git log -1 --format=%ct -- docs/council/ 2>/dev/null || echo 0)
COUNCIL_TS=${COUNCIL_TS:-0}

# UNCOMMITTED infra changes count as newer than any council, always. Found by using
# this hook: comparing committed timestamps alone means edits sitting in the working
# tree are invisible to it, so anyone can edit infra/ and apply with a stale council
# still satisfying the check -- which is exactly how several applies got through on
# the day this was written. The artifact must review what is about to be APPLIED, and
# what is about to be applied is the working tree, not the last commit.
DIRTY=$(cd "$REPO" && git status --porcelain -- infra/ '*.tf' 2>/dev/null | head -20)

if [ -n "$DIRTY" ]; then
    REASON=$(printf 'Infrastructure mutation BLOCKED -- uncommitted changes under infra/.

%s

The council record reviews what is COMMITTED, so an apply from a dirty working tree
applies something no council has seen -- however fresh the record looks. Commit the
infra change together with the council record that covers it, then re-run.

Read-only work is never blocked: plan, validate, fmt, init, show, and every
read-only cloud API call.' "$DIRTY")
    jq -cn --arg r "$REASON" '{decision:"block", reason:$r, hookSpecificOutput:{hookEventName:"PreToolUse", permissionDecision:"deny", permissionDecisionReason:$r}}'
    exit 0
fi

if [ -d "$COUNCIL_DIR" ] && [ "$COUNCIL_TS" -gt 0 ] && [ "$COUNCIL_TS" -ge "$INFRA_TS" ]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# 3. Block, and say exactly what would satisfy the gate
# ---------------------------------------------------------------------------
if [ ! -d "$COUNCIL_DIR" ] || [ "$COUNCIL_TS" -eq 0 ]; then
    DETAIL='No council record exists in docs/council/ at all.'
else
    DETAIL=$(printf 'The newest council record PRE-DATES the newest infra change.\n  infra/ last committed:          %s\n  docs/council/ last committed:   %s\n\nA council that predates the infrastructure it approves reviewed something else.' \
        "$(cd "$REPO" && date -r "$INFRA_TS" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "$INFRA_TS")" \
        "$(cd "$REPO" && date -r "$COUNCIL_TS" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "$COUNCIL_TS")")
fi

REASON=$(printf 'Infrastructure mutation BLOCKED -- no council review in the development graph.

Command: %s

%s

No infra deployment goes through without a council review recorded as an
artifact, not held in a conversation.

TO SATISFY THIS GATE:
  1. Run a multi-agent council over the pending change. Minimum four lenses,
     each an independent agent, none of them the author:
       - reliability / observability   (what failure is NOT alarmed?)
       - security / IAM blast radius   (least privilege, secret paths, state)
       - IaC architecture & delivery   (drift, reproducibility, CI vs local)
       - cost / operational burden     (right-sizing, recurring toil)
  2. Write the verdict to docs/council/<YYYY-MM-DD>-<topic>.md. Record the
     DISAGREEMENTS and what was rejected, not just the approvals -- a council
     record with no dissent is a rubber stamp, and reads as one later.
  3. COMMIT it. The gate compares committed timestamps, so an uncommitted file
     does not count. That is deliberate: the artifact must be in the graph.
  4. Re-run this command.

Read-only work is never blocked: terraform plan / validate / fmt / init / show,
and every read-only AWS call. Verify as much as you like before the council.' "$CMD" "$DETAIL")

jq -cn --arg r "$REASON" '{decision:"block", reason:$r, hookSpecificOutput:{hookEventName:"PreToolUse", permissionDecision:"deny", permissionDecisionReason:$r}}'
exit 0
