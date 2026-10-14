#!/usr/bin/env python3
"""Q1 computation entry; shared audited formulas are in gpu_scheduling.q1."""
import argparse
import json
from pathlib import Path
import sys
PROBLEM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROBLEM / "src"))
from gpu_scheduling.q1 import analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PROBLEM / "data/raw", help="CSV directory or original data ZIP")
    parser.add_argument("--out", type=Path, required=True, help="New output directory; existing results are preserved")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output exists; choose a new directory")
    _, _, stats = analyze(args.data, args.out)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
