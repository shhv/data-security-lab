"""Quick look: how does one classifier do on the labeled set?

    python -m eval.score                       # default regex classifier
    python -m eval.score --classifier regex-only
    python -m eval.score --show fn --category obfuscated

Full comparison report (latency, cost, consistency, Markdown/CSV) is eval.compare (Step 4).
"""

import argparse
from pathlib import Path

from datagen.evalset import load
from dspm.classifiers import DEFAULT, get_classifier

from .scoring import TYPES, counts, evaluate, prf


def table(title: str, groups: dict) -> None:
    print(f"\n{title:14} {'TP':>4} {'FP':>4} {'FN':>4}  {'prec':>5} {'recall':>6} {'F1':>5}")
    total = {"tp": 0, "fp": 0, "fn": 0}
    for k in sorted(groups):
        c = groups[k]
        p, r, f = prf(c)
        print(f"{k:14} {c['tp']:4} {c['fp']:4} {c['fn']:4}  {p:5.2f} {r:6.2f} {f:5.2f}")
        for x in total:
            total[x] += c[x]
    from collections import Counter
    p, r, f = prf(Counter(total))
    print(f"{'OVERALL':14} {total['tp']:4} {total['fp']:4} {total['fn']:4}  {p:5.2f} {r:6.2f} {f:5.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab", default="lab_data")
    ap.add_argument("--classifier", default=DEFAULT)
    ap.add_argument("--show", choices=["fp", "fn"], help="list the mistakes")
    ap.add_argument("--category", help="only snippets in this category")
    args = ap.parse_args()

    snippets = load(Path(args.lab))
    if args.category:
        snippets = [s for s in snippets if s["category"] == args.category]
    clf = get_classifier(args.classifier)
    res = evaluate(clf, snippets)
    print(f"classifier: {clf.name}   snippets: {len(snippets)}")
    by_type = counts(res, lambda s, t: t)
    table("type", {t: by_type[t] for t in TYPES})
    table("category", counts(res, lambda s, t: s["category"]))

    if args.show == "fp":
        print("\nFALSE POSITIVES (flagged, but not sensitive):")
        for s, f in res.fp:
            print(f"  [{s['id']}] {f.type:11} {f.value!r:24} in: {s['text']}")
    if args.show == "fn":
        print("\nFALSE NEGATIVES (sensitive, but missed):")
        for s, lab in res.fn:
            print(f"  [{s['id']}] {lab['type']:11} {lab['value']!r:40.40}  ({s['note']})")


if __name__ == "__main__":
    main()
