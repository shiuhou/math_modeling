#!/usr/bin/env python3
"""Summarize short single-worker and gang waiting from persisted job times.

This is a read-only diagnostic for completed runs.  It does not evaluate or
change scheduler decisions and deliberately reports only the requested
duration/worker strata.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path

import numpy as np


def read_times(path: Path) -> dict[int, dict[str, int]]:
    with gzip.open(path, "rt", newline="") as handle:
        rows = csv.DictReader(handle)
        result: dict[int, dict[str, int]] = {}
        for row in rows:
            jid = int(row["job_name"])
            if jid in result:
                raise ValueError(f"duplicate job_name: {jid}")
            result[jid] = {
                "duration": int(row["duration"]),
                "worker_num": int(row["worker_num"]),
                "wait": int(row["start"]) - int(row["submit_time"]),
            }
    return result


def strata(times: dict[int, dict[str, int]]) -> dict[str, dict[str, float | int]]:
    groups = {
        "short_single_worker": lambda x: x["duration"] <= 3600 and x["worker_num"] == 1,
        "short_multi_worker": lambda x: x["duration"] <= 3600 and x["worker_num"] > 1,
        "long_multi_worker": lambda x: x["duration"] > 3600 and x["worker_num"] > 1,
    }
    out: dict[str, dict[str, float | int]] = {}
    for name, predicate in groups.items():
        waits = np.asarray([x["wait"] for x in times.values() if predicate(x)], dtype=np.int64)
        if not len(waits):
            out[name] = {"n": 0, "mean_wait_hours": None, "p99_wait_hours": None,
                         "max_wait_hours": None}
            continue
        out[name] = {
            "n": int(len(waits)),
            "mean_wait_hours": float(waits.mean() / 3600),
            "p99_wait_hours": float(np.quantile(waits, 0.99) / 3600),
            "max_wait_hours": float(waits.max() / 3600),
        }
    return out


def pair(base: dict[int, dict[str, int]], other: dict[int, dict[str, int]]) -> dict[str, dict[str, int]]:
    if set(base) != set(other):
        raise ValueError("paired job sets differ")
    groups = {
        "short_single_worker": lambda x: x["duration"] <= 3600 and x["worker_num"] == 1,
        "short_multi_worker": lambda x: x["duration"] <= 3600 and x["worker_num"] > 1,
        "long_multi_worker": lambda x: x["duration"] > 3600 and x["worker_num"] > 1,
    }
    result = {}
    for name, predicate in groups.items():
        deltas = [other[j]["wait"] - base[j]["wait"] for j in base if predicate(base[j])]
        result[name] = {"n": len(deltas), "improved_jobs": sum(d < 0 for d in deltas),
                        "worsened_jobs": sum(d > 0 for d in deltas),
                        "unchanged_jobs": sum(d == 0 for d in deltas)}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--times", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compare-times", type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output exists; choose a new path")
    current = read_times(args.times)
    payload = {"schema_version": 1, "kind": "gang_starvation_diagnostic",
               "source": str(args.times), "jobs": len(current), "strata": strata(current)}
    if args.compare_times:
        other = read_times(args.compare_times)
        payload["comparison"] = {"baseline": str(args.times), "candidate": str(args.compare_times),
                                  "strata": pair(current, other)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
