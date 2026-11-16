"""Span-level scoring.

Matching rule for one snippet:
- A finding MATCHES a label if the types are equal AND their character spans overlap.
- A finding with span=None (an LLM that can't point at characters) matches any unmatched
  label of the same type. That's more lenient, and the report should say so.
- Each label can be matched once. Unmatched findings = FP, unmatched labels = FN.

Why overlap and not exact span? "SSN: 912-34-5678" - whether a classifier includes the
"SSN: " prefix shouldn't decide right vs wrong. What matters for DLP is: did it find it?
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from dspm.classifiers import Finding

TYPES = ["ssn", "credit_card", "email", "health", "salary", "address"]


@dataclass
class Result:
    tp: list = field(default_factory=list)   # (snippet, finding, label)
    fp: list = field(default_factory=list)   # (snippet, finding)
    fn: list = field(default_factory=list)   # (snippet, label)


def match(snippet: dict, findings: list[Finding], res: Result) -> None:
    unmatched = list(snippet["labels"])
    for f in findings:
        hit = None
        for lab in unmatched:
            if lab["type"] != f.type:
                continue
            if f.span is None or (f.span[0] < lab["end"] and lab["start"] < f.span[1]):
                hit = lab
                break
        if hit:
            unmatched.remove(hit)
            res.tp.append((snippet, f, hit))
        else:
            res.fp.append((snippet, f))
    res.fn.extend((snippet, lab) for lab in unmatched)


def counts(res: Result, key) -> dict[str, Counter]:
    """Group TP/FP/FN by key(snippet, type) -> e.g. per data type or per category."""
    out: dict[str, Counter] = defaultdict(Counter)
    for s, f, _ in res.tp:
        out[key(s, f.type)]["tp"] += 1
    for s, f in res.fp:
        out[key(s, f.type)]["fp"] += 1
    for s, lab in res.fn:
        out[key(s, lab["type"])]["fn"] += 1
    return out


def prf(c: Counter) -> tuple[float, float, float]:
    p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
    r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def evaluate(classifier, snippets: list[dict]) -> Result:
    res = Result()
    for s in snippets:
        match(s, classifier.classify(s["text"]), res)
    return res
