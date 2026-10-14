#!/usr/bin/env python3
"""Run bounded M2-B cost probes with one clean child process per policy.

The child is the existing single DES pressure runner.  This wrapper only
coordinates independent invocations and records their summaries, so each
policy has its own peak RSS and cannot inherit a previous strategy's
``ru_maxrss``.  Full per-job outputs stay in the ignored output directory;
the committed evidence is the compact benchmark summary and hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

PROBLEM = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PROBLEM / "data/raw")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="A10")
    parser.add_argument("--jobs", type=int, nargs="+", default=[16_384, 32_768])
    parser.add_argument("--theta-seconds", type=int, nargs="+", default=[4_860_000])
    parser.add_argument("--short-theta-seconds", type=int, default=4)
    parser.add_argument("--reservation-k", type=int, default=200)
    parser.add_argument("--event-mode", choices=("shared-timer", "arrival-completion-only"), default="shared-timer")
    parser.add_argument("--policies", nargs="+",
                        default=["SPT-URGENT-TIME", "SPT-URGENT-FIXED", "SPT-URGENT-FLEX", "EASY-NR"])
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output exists; choose a new directory")
    if any(n <= 0 for n in args.jobs) or any(t < 0 for t in args.theta_seconds) or args.short_theta_seconds < 0:
        parser.error("jobs and thresholds must be nonnegative (jobs strictly positive)")
    args.out.mkdir(parents=True)
    records = []
    probe_specs = [(int(n), int(theta), "historical-anchor")
                   for n in args.jobs for theta in args.theta_seconds]
    if args.short_theta_seconds not in args.theta_seconds:
        probe_specs.append((min(args.jobs), int(args.short_theta_seconds), "mechanism-short-threshold"))
    runner = PROBLEM / "experiments" / "run_m2a_pressure.py"
    for jobs, theta, threshold_label in probe_specs:
        for policy in args.policies:
            tag = f"{args.model.lower()}-{jobs}-theta{theta}-{policy.lower()}"
            child_out = args.out / tag
            started = time.perf_counter()
            command = [sys.executable, str(runner), "--data", str(args.data),
                       "--out", str(child_out), "--model", args.model,
                       "--jobs", str(jobs), "--theta-seconds", str(theta),
                       "--reservation-k", str(args.reservation_k), "--event-mode", args.event_mode,
                       "--policies", policy]
            completed = subprocess.run(command, text=True, capture_output=True)
            wall = time.perf_counter() - started
            if completed.returncode != 0:
                raise RuntimeError(f"child failed ({tag})\n{completed.stdout}\n{completed.stderr}")
            summary_path = child_out / "summary.json"
            summary = json.loads(summary_path.read_text())
            child = summary["results"][0]
            records.append({
                "jobs": jobs, "theta_seconds": theta, "threshold_label": threshold_label,
                "policy": child["policy"], "child_output": str(child_out.relative_to(args.out)),
                "child_wall_seconds": wall, "child_summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
                "peak_rss_kib_process": child["peak_rss_kib_process"],
                "scheduler_seconds": child["scheduler_seconds"],
                "validation_seconds": child["validation_seconds"],
                "metrics_seconds": child["metrics_seconds"], "io_seconds": child["io_seconds"],
                "input_seconds": child["input_seconds"], "runtime_seconds": child["runtime_seconds"],
                "schedule_sha256": child["schedule_sha256"], "reservations": child["reservations"],
                "cost": child["cost"], "metrics": child["metrics"],
                "validation": child["validation"],
            })
    output = {
        "schema_version": 1, "kind": "m2b_bounded_cost_probe",
        "configuration": {"model": args.model, "jobs": args.jobs, "theta_seconds": args.theta_seconds,
                          "short_theta_seconds": args.short_theta_seconds,
                          "reservation_k": args.reservation_k, "event_mode": args.event_mode,
                          "policies": args.policies, "placement": "first-fit ascending node_name",
                          "horizon_seconds": 7_776_000},
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "records": records,
        "note": "Each record is an independent child process; no performance claim is made for unrun full trace.",
    }
    path = args.out / "benchmark.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
