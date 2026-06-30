#!/usr/bin/env python3
"""Detection engine for two assertion classes that, like Lesson 2, are claims the
state-checks miss when stated without a probe:

  * ABSENCE  (Lessons 12 + 15) -- "couldn't find X", "no such cron", "the table
    is empty", "doesn't exist". A negative result asserted without a full search
    (L15) or adopted from a subagent's "empty/missing" without an independent
    probe (L12). "No cron exists" is not "the table is empty."
  * STATE-CHAIN (Lesson 11) -- a downstream state inferred from an upstream
    signal: "merged so it's live", "pushed therefore in main", "deployed so it
    works". The green badge is not the outcome.

A claim is flagged only when its turn shows NO probe tool-call (grep/find/Read/
psql/git show/ls-remote/curl/gh ...) and the sentence carries no evidence tag
([verified:]/[hypothesis:]/[searched:]). The per-turn probe check keeps the
signal high -- a claim made right after a real search is left alone.

Heuristic, like its sibling diagnosis-evidence-audit: catches the high-signal
shape, accepts a miss rate, exists to make the re-violation visible.

Modes (argv[1]): --file <path> | --stop (stdin Stop JSON) | --digest <paths...>
"""

import json
import os
import re
import sys

TAG = re.compile(
    r"\[(?:verified|hypothesis|unverified|assumed|to[- ]verify|probe|conf|"
    r"source|searched)\b",
    re.I,
)
ABSENCE = re.compile(
    r"(could ?n'?t find|not found|no (?:record|results?|trace|sign|cron|rows?|"
    r"match(?:es)?|entry|entries|reference)|nothing (?:found|matched|there)|"
    r"does(?: ?n'?t| not) exist|is ?n'?t (?:there|present|defined)|no such|"
    r"came up empty|returned nothing|(?:table|set|result) is empty|"
    r"there (?:is|are) no\b)",
    re.I,
)
STATE_CHAIN = re.compile(
    r"\b(pushed|merged|deployed|applied|built|green|passed|the badge)\b"
    r"[^.\n]{0,45}\b(so|therefore|which means|hence|means it'?s?|=>|->)\b"
    r"[^.\n]{0,45}\b(live|in (?:main|prod|production)|deployed|working|works|"
    r"done|shipped|applied|landed|in main|complete)\b",
    re.I,
)
PROBE_BASH = re.compile(
    r"\b(grep|rg |ripgrep|find |fd |ls |psql|select |count\(|git show|"
    r"git ls-remote|git rev-parse|git log|curl|gh api|gh run|gh pr |cat |jq |"
    r"analytics/reports|sf\.|\\d |information_schema)\b",
    re.I,
)
PROBE_TOOLS = {"Grep", "Glob", "Read", "WebFetch", "WebSearch"}


def sentences(text):
    for chunk in re.split(r"(?<=[.\n!?])\s+", text):
        chunk = chunk.strip()
        if chunk:
            yield chunk


def _content_blocks(ev):
    content = ev.get("content")
    if content is None:
        content = ev.get("message", {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return content
    return []


def turns(path):
    """Yield (turn_idx, assistant_text, had_probe) per assistant turn. had_probe
    is True if any probe tool-call appeared in the turn (assistant tool_use or a
    Bash command matching PROBE_BASH). Falls back to a single plain-text blob."""
    turn = 0
    saw_json = False
    cur_text, cur_probe = [], False

    def flush():
        if cur_text:
            return (turn, "\n".join(cur_text), cur_probe)
        return None

    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        saw_json = True
        role = ev.get("role") or ev.get("message", {}).get("role")
        is_user = role == "user" or ev.get("type") == "user"
        is_asst = role == "assistant" or ev.get("type") == "assistant"
        if is_user:
            out = flush()
            if out:
                yield out
            turn += 1
            cur_text, cur_probe = [], False
            # a tool_result lives in a user event; its presence doesn't probe,
            # but the originating tool_use (assistant) was already counted.
            continue
        if is_asst:
            for b in _content_blocks(ev):
                if not isinstance(b, dict):
                    if isinstance(b, str):
                        cur_text.append(b)
                    continue
                t = b.get("type")
                if t == "text":
                    cur_text.append(b.get("text", ""))
                elif t == "tool_use":
                    name = b.get("name", "")
                    if name in PROBE_TOOLS:
                        cur_probe = True
                    elif name == "Bash":
                        cmd = (b.get("input", {}) or {}).get("command", "")
                        if PROBE_BASH.search(cmd):
                            cur_probe = True
    out = flush()
    if out:
        yield out
    if not saw_json:
        try:
            with open(path, encoding="utf-8") as fh:
                yield (0, fh.read(), False)
        except OSError:
            return


def scan(path, last_only=False):
    items = list(turns(path))
    if last_only and items:
        items = items[-1:]
    flags = []
    for turn, text, had_probe in items:
        if had_probe:
            continue
        for sent in sentences(text):
            if TAG.search(sent):
                continue
            kind = None
            if ABSENCE.search(sent):
                kind = "absence"
            elif STATE_CHAIN.search(sent):
                kind = "state-chain"
            if kind:
                flags.append((turn, kind, re.sub(r"\s+", " ", sent)[:160]))
    return flags


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--digest"

    if mode == "--file":
        flags = scan(sys.argv[2])
        for t, kind, s in flags:
            print(f"{t}\t{kind}\t{s}")
        sys.exit(1 if flags else 0)

    if mode == "--stop":
        try:
            data = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            sys.exit(0)
        if data.get("stop_hook_active"):
            sys.exit(0)
        tp = data.get("transcript_path", "")
        if not tp or not os.path.exists(tp):
            sys.exit(0)
        flags = scan(tp, last_only=True)
        if flags:
            snips = "; ".join(f"({k}) {s}" for _, k, s in flags[:4])
            reason = (
                "claim-evidence-audit (Lessons 11/12/15): your last message makes "
                f"{len(flags)} absence/state claim(s) with no probe this turn and no "
                f"tag -- {snips}. Before finishing: for an absence claim, search the "
                "FULL corpus (and verify a subagent's 'empty/missing' against live "
                "state); for a state claim, probe the downstream state itself "
                "(ls-remote / git show / the live surface), not the upstream badge. "
                "Then tag [verified: <probe>] or [searched: <scope>]. See "
                "~/claude-code-mastery LESSONS Lessons 11, 12, 15."
            )
            print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)

    for f in sys.argv[2:]:
        flags = scan(f)
        if flags:
            print(
                f"  {len(flags)} untagged absence/state claim(s) in {os.path.basename(f)}"
            )
            for _, kind, s in flags[:3]:
                print(f"    > ({kind}) {s}")
    sys.exit(0)


if __name__ == "__main__":
    main()
