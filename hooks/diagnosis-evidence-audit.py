#!/usr/bin/env python3
"""Detection engine for Lesson 2 -- a causal claim about a discrepancy stated as
fact without a source-of-truth probe (and without a [hypothesis:] tag).

Modes (dispatched by argv[1]):
  --file  <path>     scan a transcript (jsonl or plain text); print one line per
                     flagged assertion ("<turn>\\t<snippet>"); exit 1 if any.
  --stop             read a Stop-hook JSON event on stdin; scan ONLY the last
                     assistant turn; emit {"decision":"block","reason":...} when
                     an untagged causal/external diagnosis is found. Loop-guarded
                     via stop_hook_active. Always exit 0.
  --digest <paths>   scan each path; print a short digest; exit 0 (SessionStart).

Heuristic by design (this class is judgment-heavy, cf. ledger L11/L15/L16): it
catches the high-signal shape -- a causal connector co-occurring with an
external/uncertainty suspect, UNTAGGED -- and accepts a miss/false-positive rate.
Its job is to make the re-violation visible, not to prove correctness.
"""

import json
import os
import re
import sys

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
# Evidence tag (the cheap escape hatch the forcing-format convention provides).
TAG = re.compile(
    r"\[(?:verified|hypothesis|unverified|assumed|to[- ]verify|probe|conf|"
    r"source)\b",
    re.I,
)
# A live probe verb adjacent to the claim also satisfies "this was checked".
PROBE = re.compile(
    r"\b(queried|query the|ran the|pulled the|fetched the|read the source|"
    r"checked the (?:source|report|table|db)|select |count\(|"
    r"analytics/reports|sf\.|psql|git show origin|ls-remote)\b",
    re.I,
)


def sentences(text):
    for chunk in re.split(r"(?<=[.\n!?])\s+", text):
        chunk = chunk.strip()
        if chunk:
            yield chunk


def assistant_texts(path):
    """Yield (turn_index, text) per assistant text block. Accepts Claude
    transcript JSONL or, as a fallback, a plain-text blob."""
    turn = 0
    saw_json = False
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
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
                    turn += 1
                    continue
                if role == "assistant" or ev.get("type") == "assistant":
                    content = ev.get("content")
                    if content is None:
                        content = ev.get("message", {}).get("content")
                    parts = []
                    if isinstance(content, str):
                        parts.append(content)
                    elif isinstance(content, list):
                        for b in content:
                            if isinstance(b, dict) and b.get("type") == "text":
                                parts.append(b.get("text", ""))
                            elif isinstance(b, str):
                                parts.append(b)
                    if parts:
                        yield turn, "\n".join(parts)
    except FileNotFoundError:
        return
    if not saw_json:
        try:
            with open(path, encoding="utf-8") as fh:
                yield 0, fh.read()
        except OSError:
            return


def scan(path, last_only=False):
    items = list(assistant_texts(path))
    if last_only and items:
        items = items[-1:]
    flags = []
    for turn, text in items:
        for sent in sentences(text):
            if not (CONNECTOR.search(sent) and SUSPECT.search(sent)):
                continue
            if TAG.search(sent) or PROBE.search(sent):
                continue
            flags.append((turn, re.sub(r"\s+", " ", sent)[:160]))
    return flags


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--digest"

    if mode == "--file":
        flags = scan(sys.argv[2])
        for t, s in flags:
            print(f"{t}\t{s}")
        sys.exit(1 if flags else 0)

    if mode == "--stop":
        try:
            data = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            sys.exit(0)
        if data.get("stop_hook_active"):
            sys.exit(0)  # loop guard: already continuing from a stop hook
        tp = data.get("transcript_path", "")
        if not tp or not os.path.exists(tp):
            sys.exit(0)
        flags = scan(tp, last_only=True)
        if flags:
            snippets = "; ".join(s for _, s in flags[:4])
            reason = (
                "diagnosis-evidence-audit (Lesson 2): your last message asserts "
                f"{len(flags)} causal/external diagnosis(es) with no source-of-truth "
                "probe and no evidence tag -- "
                f"{snippets}. Before finishing: probe the source that adjudicates "
                "it, then tag each claim [verified: <probe>] or [hypothesis: <probe>], "
                "or drop the causal claim. A cause that fits the gap is not a cause "
                "that has been shown. See ~/claude-code-mastery CLAUDE.md "
                "Ground-Truth table + LESSONS Lesson 2."
            )
            print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)

    # --digest (SessionStart): scan each path arg, print short digest, never block
    for f in sys.argv[2:]:
        flags = scan(f)
        if flags:
            print(
                f"  {len(flags)} untagged causal/external diagnosis(es) in {os.path.basename(f)}"
            )
            for _, s in flags[:3]:
                print(f"    > {s}")
    sys.exit(0)


if __name__ == "__main__":
    main()
