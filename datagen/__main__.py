"""CLI: python -m datagen --out lab_data --seed 42"""

import argparse
import json

from .generate import generate


def main() -> None:
    p = argparse.ArgumentParser(description="Generate the synthetic DSPM/DLP lab dataset.")
    p.add_argument("--out", default="lab_data", help="output directory (wiped first)")
    p.add_argument("--seed", type=int, default=42, help="same seed => identical lab")
    args = p.parse_args()
    summary = generate(args.out, args.seed)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
