"""Score each deterministic layer against the generator's answer key.

    python -m dspm.compare_levels lab_data

Scoring is COUNT-based per file: TP = min(found, truth), FP = excess, FN = shortfall.
Limitation (on purpose, fixed in Stage 6 step 2): if a detector misses one real SSN and
flags one decoy in the same file, counts cancel and it looks perfect. Span-level labels
are needed to catch that.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .classifiers import REGISTRY, get_classifier

TYPES = ["ssn", "credit_card", "email", "health_record"]


def score(lab: Path, name: str, **kw) -> dict[str, Counter]:
    manifest = json.loads((lab / "manifest.json").read_text())
    root = lab / "storage" / manifest["account"]
    clf = get_classifier(name, **kw)
    stats = {t: Counter() for t in TYPES}
    for rel, meta in manifest["files"].items():
        found = clf.counts((root / rel).read_text(encoding="utf-8"))
        for t in TYPES:
            truth, got = meta["truth"].get(t, 0), found.get(t, 0)
            stats[t]["tp"] += min(truth, got)
            stats[t]["fp"] += max(0, got - truth)
            stats[t]["fn"] += max(0, truth - got)
    return stats


def prf(c: Counter) -> tuple[float, float, float]:
    p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
    r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("lab", nargs="?", default="lab_data")
    ap.add_argument("--production-ssn-rules", action="store_true",
                    help="reject 9xx SSN areas like a real validator would")
    args = ap.parse_args()
    lab = Path(args.lab)
    print(f"{'classifier':16} {'type':13} {'TP':>4} {'FP':>4} {'FN':>4}  {'prec':>5} {'recall':>6} {'F1':>5}")
    for name in REGISTRY:
        kw = {"allow_lab_ssn_area": False} if args.production_ssn_rules and name != "regex-only" else {}
        for t, c in score(lab, name, **kw).items():
            p, r, f = prf(c)
            print(f"{name:16} {t:13} {c['tp']:4} {c['fp']:4} {c['fn']:4}  {p:5.2f} {r:6.2f} {f:5.2f}")
        print()


if __name__ == "__main__":
    main()
