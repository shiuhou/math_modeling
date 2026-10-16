#!/usr/bin/env python3
"""Compare TIME, FIXED and FLEX job-level outcomes in one M2-D run.

The comparison is deliberately paired by job_name within an identical
jobs/theta/event-mode configuration.  It does not select a best threshold or
infer a causal performance claim; it records which jobs changed and whether
zero-wait jobs acquired delay.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np


def read_times(path: Path) -> dict[int, dict[str, int]]:
    with gzip.open(path, "rt", newline="") as handle:
        rows = csv.DictReader(handle)
        out = {}
        for row in rows:
            jid = int(row["job_name"])
            if jid in out:
                raise ValueError(f"duplicate job_name in {path}: {jid}")
            out[jid] = {
                "duration": int(row["duration"]),
                "submit_time": int(row["submit_time"]),
                "wait": int(row["start"]) - int(row["submit_time"]),
                "start": int(row["start"]),
                "finish": int(row["finish"]),
            }
    return out


def compare(base: dict[int, dict[str, int]], other: dict[int, dict[str, int]]) -> dict:
    ids = sorted(set(base) & set(other))
    if len(ids) != len(base) or len(ids) != len(other):
        raise ValueError("paired outputs have different job sets")
    if any((base[j]["duration"], base[j]["submit_time"]) !=
           (other[j]["duration"], other[j]["submit_time"]) for j in ids):
        raise ValueError("paired outputs have different inputs")
    delta = np.asarray([other[j]["wait"] - base[j]["wait"] for j in ids], dtype=np.int64)
    base_wait = np.asarray([base[j]["wait"] for j in ids], dtype=np.int64)
    durations = np.asarray([base[j]["duration"] for j in ids], dtype=np.int64)
    changed = delta != 0
    return {
        "jobs": len(ids),
        "mean_wait_delta_hours": float(delta.mean() / 3600),
        "p95_wait_delta_hours": float(np.quantile(delta, .95) / 3600),
        "max_wait_delta_hours": float(delta.max() / 3600),
        "improved_jobs": int((delta < 0).sum()),
        "worsened_jobs": int((delta > 0).sum()),
        "unchanged_jobs": int((delta == 0).sum()),
        "changed_jobs": int(changed.sum()),
        "base_zero_wait_jobs": int((base_wait == 0).sum()),
        "base_zero_wait_new_delay_jobs": int(((base_wait == 0) & (delta > 0)).sum()),
        "long_jobs_duration_ge_p95": int((durations >= np.quantile(durations, .95)).sum()),
        "long_jobs_improved": int(((durations >= np.quantile(durations, .95)) & (delta < 0)).sum()),
        "long_jobs_worsened": int(((durations >= np.quantile(durations, .95)) & (delta > 0)).sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output exists; choose a new path")
    benchmark = json.loads((args.benchmark / "benchmark.json").read_text())
    records = [r for r in benchmark["records"] if r.get("status", "PASS") == "PASS"]
    groups = {}
    for record in records:
        key = (int(record["jobs"]), int(record["theta_seconds"]))
        groups.setdefault(key, {})[record["policy"]] = record
    output = {"schema_version": 1, "kind": "m2d_paired_analysis",
              "benchmark_sha256": hashlib.sha256((args.benchmark / "benchmark.json").read_bytes()).hexdigest(),
              "comparisons": []}
    for (jobs, theta), group in sorted(groups.items()):
        if "SPT-URGENT-TIME" not in group:
            continue
        for baseline, policy in (("SPT-URGENT-TIME", "SPT-URGENT-FIXED"),
                                 ("SPT-URGENT-TIME", "SPT-URGENT-FLEX"),
                                 ("SPT-URGENT-FIXED", "SPT-URGENT-FLEX")):
            if baseline not in group or policy not in group:
                continue
            base = read_times(args.benchmark / group[baseline]["child_output"] /
                              f"{baseline}_job_times.csv.gz")
            other = read_times(args.benchmark / group[policy]["child_output"] /
                               f"{policy}_job_times.csv.gz")
            pair_result = compare(base, other)
            detail = args.benchmark / f"paired-{jobs}-{theta}-{baseline}-to-{policy}.csv.gz"
            if detail.exists():
                raise ValueError(f"paired detail exists: {detail}")
            with gzip.open(detail, "wt", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["job_name", "duration_seconds", "baseline_wait_seconds",
                                 "candidate_wait_seconds", "wait_delta_seconds"])
                for jid in sorted(base):
                    writer.writerow([jid, base[jid]["duration"], base[jid]["wait"],
                                     other[jid]["wait"], other[jid]["wait"] - base[jid]["wait"]])
            output["comparisons"].append({"jobs": jobs, "theta_seconds": theta,
                "baseline": baseline, "policy": policy, "result": pair_result,
                "detail": detail.name,
                "detail_sha256": hashlib.sha256(detail.read_bytes()).hexdigest()})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
