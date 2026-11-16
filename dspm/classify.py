"""Scan a file, a folder, or a piece of text and print what was found.

    python -m dspm.classify my_test.txt
    python -m dspm.classify lab_data/storage
    python -m dspm.classify --text "ssn 912-34-5678"
    python -m dspm.classify my_test.txt --classifier regex-only
"""

import argparse
from pathlib import Path

from .classifiers import DEFAULT, REGISTRY, get_classifier


def show(label: str, text: str, clf) -> None:
    findings = clf.classify(text)
    print(f"\n{label}: {len(findings)} finding(s)")
    for f in findings:
        print(f"  {f.type:12} {f.value!r:28} conf={f.confidence:.2f}  {f.explanation}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="file or folder to scan")
    ap.add_argument("--text", help="classify this string instead of a file")
    ap.add_argument("--classifier", default=DEFAULT, help=f"one of {sorted(REGISTRY)} or 'regex'")
    args = ap.parse_args()
    clf = get_classifier(args.classifier)
    print(f"classifier: {clf.name}")
    if args.text is not None:
        show("text", args.text, clf)
    elif args.path:
        p = Path(args.path)
        for f in sorted([p] if p.is_file() else (x for x in p.rglob("*") if x.is_file())):
            show(str(f), f.read_text(encoding="utf-8", errors="replace"), clf)
    else:
        ap.error("give a path or --text")


if __name__ == "__main__":
    main()
