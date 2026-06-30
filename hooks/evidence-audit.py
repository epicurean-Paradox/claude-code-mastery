#!/usr/bin/env python3
"""Unified evidence-audit engine -- one transcript walker, three rule families.
Replaces the former diagnosis-evidence-audit + claim-evidence-audit pair (same
detection, half the maintenance surface).

Families:
  causal      (Lesson 2)        -- a causal connector co-occurring with an
                                    external/uncertainty suspect, stated as fact
                                    ("the difference is a snapshot", "242 vs local").
  absence     (Lessons 12 + 15) -- a negative asserted without a search
                                    ("couldn't find", "no such cron", "empty").
  state-chain (Lesson 11)       -- a downstream state inferred from an upstream
                                    signal ("merged so it's live").

Suppression differs by family -- this is why the families stay distinct even
though the plumbing is shared:
  - causal     -> suppressed ONLY by an inline evidence tag or an inline probe
                  verb in the SAME sentence. NOT by a turn-level probe: the L2
                  failure ("the 527K is the 242 snapshot") was stated in a turn
                  full of psql calls that probed the WRONG source, so turn-level
                  suppression would miss the exact case the family exists for.
  - absence /
    state-chain -> suppressed by an inline tag OR any probe tool-call in the same
                   turn (a "couldn't find" right after a grep is fine).

Modes (argv[1]): --file <path> | --stop (stdin Stop JSON) | --digest <paths...>
Heuristic by design (judgment-heavy class, cf. ledger L11/L15/L16): makes
re-violations visible, does not prove correctness.
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

# --- causal (Lesson 2) ---
CONNECTOR = re.compile(
    r"\b(because|due to|caused by|the reason|root cause|explained by|"
    r"comes down to|boils down to|attributable to|the difference is|"
    r"the gap is|that'?s (?:just )?(?:a|the|because)|is (?:just )?(?:a|the))\b",
    re.I,
)
SUSPECT = re.compile(
    r"\b(snapshot|stale(?:ness)?|deploy(?:ed|ment)?|cache[d]?|timing|"
    r"race(?: condition)?|environment|env diff|proxy|version skew|drift|"
    r"out of sync|not a (?:code )?bug|data[- ]snapshot|cloud[- ]vs[- ]local|"
    r"local[- ]vs[- ]cloud|242|different snapshot|point[- ]in[- ]time)\b",
    re.I,
)
INLINE_PROBE = re.compile(
    r"\b(queried|query the|ran the|pulled the|fetched the|read the source|"
    r"checked the (?:source|report|table|db)|select |count\(|"
    r"analytics/reports|sf\.|psql|git show origin|ls-remote)\b",
    re.I,
)

# --- absence (Lessons 12 + 15) ---
ABSENCE = re.compile(
    r"(could ?n'?t find|not found|no (?:record|results?|trace|sign|cron|rows?|"
    r"match(?:es)?|entry|entries|reference)|nothing (?:found|matched|there)|"
    r"does(?: ?n'?t| not) exist|is ?n'?t (?:there|present|defined)|no such|"
    r"came up empty|returned nothing|(?:table|set|result) is empty|"
    r"there (?:is|are) no\b)",
    re.I,
)

# --- state-chain (Lesson 11) ---
STATE_CHAIN = re.compile(
    r"\b(pushed|merged|deployed|applied|built|green|passed|the badge)\b"
    r"[^.\n]{0,45}\b(so|therefore|which means|hence|means it'?s?|=>|->)\b"
    r"[^.\n]{0,45}\b(live|in (?:main|prod|production)|deployed|working|works|"
    r"done|shipped|applied|landed|in main|complete)\b",
    re.I,
)

# --- turn-level probe detection (suppresses absence/state, not causal) ---
PROBE_BASH = re.compile(
    r"\b(grep|rg |ripgrep|find |fd |ls |psql|select |count\(|git show|"
    r"git ls-remote|git rev-parse|git log|curl|gh api|gh run|gh pr |cat |jq |"
    r"analytics/reports|sf\.|information_schema)\b",
    re.I,
)
PROBE_TOOLS = {"Grep", "Glob", "Read", "WebFetch", "WebSearch"}


def _snip(sent):
    return re.sub(r"\s+", " ", sent)[:160]


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
    is True if any probe tool-call appeared in the turn. Falls back to a single
    plain-text blob for a non-JSON file."""
    turn = 0
    saw_json = False
    cur_text, cur_probe = [], False

    def flush():
        return (turn, "\n".join(cur_text), cur_probe) if cur_text else None

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
        if role == "user" or ev.get("type") == "user":
            out = flush()
            if out:
                yield out
            turn += 1
            cur_text, cur_probe = [], False
            continue
        if role == "assistant" or ev.get("type") == "assistant":
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
        for sent in sentences(text):
            if TAG.search(sent):
                continue
            # causal: inline-only suppression (turn-level probe does NOT clear it)
            if CONNECTOR.search(sent) and SUSPECT.search(sent):
                if not INLINE_PROBE.search(sent):
                    flags.append((turn, "causal", _snip(sent)))
                continue
            # absence / state-chain: any probe this turn clears them
            if had_probe:
                continue
            if ABSENCE.search(sent):
                flags.append((turn, "absence", _snip(sent)))
            elif STATE_CHAIN.search(sent):
                flags.append((turn, "state-chain", _snip(sent)))
    return flags


_STOP_REASON = (
    "evidence-audit (Lessons 2/11/12/15): your last message makes {n} unverified "
    "claim(s) -- {snips}. Before finishing: probe the source that adjudicates it "
    "(the upstream report/log, a full corpus search, the downstream state itself -- "
    "not an upstream badge), then tag [verified: <probe>] / [hypothesis: <probe>] / "
    "[searched: <scope>], or drop the claim. A claim that fits the evidence is not "
    "one that has been shown. See ~/claude-code-mastery LESSONS Lessons 2, 11, 12, 15."
)


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
            sys.exit(0)  # loop guard
        tp = data.get("transcript_path", "")
        if not tp or not os.path.exists(tp):
            sys.exit(0)
        flags = scan(tp, last_only=True)
        if flags:
            snips = "; ".join(f"({k}) {s}" for _, k, s in flags[:4])
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": _STOP_REASON.format(n=len(flags), snips=snips),
                    }
                )
            )
        sys.exit(0)

    # --digest (SessionStart)
    for f in sys.argv[2:]:
        flags = scan(f)
        if flags:
            print(f"  {len(flags)} unverified claim(s) in {os.path.basename(f)}")
            for _, kind, s in flags[:3]:
                print(f"    > ({kind}) {s}")
    sys.exit(0)


if __name__ == "__main__":
    main()
