#!/usr/bin/env python3
"""Run a bounded A10 M2-A pressure case through the single DES.

This is an evidence runner, not a second scheduler. It persists only sparse
job timings, node placements, reservation/certificate events and a compact
cost summary; no per-reservation dense resource calendar is materialized.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
import time

PROBLEM = Path(__file__).resolve().parents[1]
REPO = PROBLEM.parents[1]
sys.path.insert(0, str(PROBLEM / "src"))
from gpu_scheduling.data import native, read_data
from gpu_scheduling.evaluation import metrics
from gpu_scheduling.simulator import POLICY_ALIASES, simulate_pool
from gpu_scheduling.validation import validate_reservations


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(native(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PROBLEM / "data/raw")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="A10")
    parser.add_argument("--jobs", type=int, default=4096)
    parser.add_argument("--theta-seconds", type=int, default=4_860_000)
    parser.add_argument("--reservation-k", type=int, default=200)
    parser.add_argument("--event-mode", choices=("shared-timer", "arrival-completion-only"), default="shared-timer")
    parser.add_argument("--policies", nargs="+", choices=sorted(POLICY_ALIASES),
                        default=["SPT-URGENT-TIME", "SPT-URGENT-FIXED", "SPT-URGENT-FLEX", "EASY-NR"])
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output exists; choose a new directory")
    if args.jobs <= 0:
        parser.error("--jobs must be positive")
    input_started = time.perf_counter()
    nodes, raw_jobs, hashes = read_data(args.data)
    jobs = raw_jobs[raw_jobs.gpu_model == args.model].head(args.jobs).copy()
    pool = nodes[nodes.gpu_model == args.model].sort_values("node_name").reset_index(drop=True)
    if len(jobs) < args.jobs:
        parser.error(f"only {len(jobs)} jobs available for {args.model}")
    args.out.mkdir(parents=True)
    input_seconds = time.perf_counter() - input_started
    run_started = time.perf_counter()
    results = []
    for requested in args.policies:
        policy_started = time.perf_counter()
        scheduler_started = time.perf_counter()
        result = simulate_pool(pool, jobs, requested, theta_seconds=args.theta_seconds,
                               reservation_k=args.reservation_k, event_mode=args.event_mode)
        scheduler_seconds = time.perf_counter() - scheduler_started
        validation_started = time.perf_counter()
        validate_reservations(pool, result["jobs"], result)
        validation_seconds = time.perf_counter() - validation_started
        metrics_started = time.perf_counter()
        metric_values = metrics(result, pool, 7_776_000)
        metrics_seconds = time.perf_counter() - metrics_started
        output_started = time.perf_counter()
        policy = result["policy"]
        with gzip.open(args.out / f"{policy}_job_times.csv.gz", "wt", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["job_name", "gpu_model", "submit_time", "duration", "worker_num",
                             "gpu_request", "cpu_request", "start", "finish"])
            for index, row in enumerate(result["jobs"].itertuples(index=False)):
                writer.writerow([int(row.job_name), row.gpu_model, int(row.submit_time), int(row.duration),
                                 int(row.worker_num), int(row.gpu_request), row.cpu_request,
                                 int(result["starts"][index]), int(result["ends"][index])])
        with gzip.open(args.out / f"{policy}_node_placements.csv.gz", "wt", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["job_name", "node_name", "workers"])
            for jid, plan in zip(result["jobs"].job_name, result["plans"]):
                writer.writerows((int(jid), int(pool.node_name.iloc[node]), int(workers)) for node, workers in plan)
        write_json(args.out / f"{policy}_reservations.json", {
            "gpu_model": args.model, "policy": policy, "event_mode": args.event_mode,
            "reservations": result["reservations"], "events": result["events"], "cost": result["cost"]})
        schedule_hash = hashlib.sha256(json.dumps({
            "starts": result["starts"].tolist(), "ends": result["ends"].tolist(),
            "plans": result["plans"]}, sort_keys=True).encode()).hexdigest()
        results.append({
            "policy": policy, "requested_policy": requested, "jobs": len(jobs),
            "runtime_seconds": time.perf_counter() - policy_started,
            # This value is per process when the runner is invoked with one
            # policy (the M2-B benchmark does exactly that).  The multi-policy
            # mode remains useful for quick local smoke runs, but its RSS is
            # explicitly labelled process-level rather than per-policy.
            "peak_rss_kib_process": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "scheduler_seconds": scheduler_seconds,
            "validation_seconds": validation_seconds,
            "metrics_seconds": metrics_seconds,
            "io_seconds": time.perf_counter() - output_started,
            "input_seconds": input_seconds,
            "metrics": metric_values,
            "schedule_sha256": schedule_hash,
            "reservations": len(result["reservations"]),
            "event_count": len(result["events"]),
            "max_certificate_updates": max((len(x.get("certificate_updates", [])) for x in result["reservations"]), default=0),
            "cost": result["cost"],
            "validation": "PASS",
        })
    summary = {
        "schema_version": 1, "kind": "m2a_pressure_run",
        "code_commit": __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "code_dirty": bool(__import__("subprocess").check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip()),
        "data_sha256": hashes, "model": args.model, "jobs": len(jobs),
        "configuration": {"policies": [r["policy"] for r in results], "theta_seconds": args.theta_seconds,
                          "reservation_k": args.reservation_k, "event_mode": args.event_mode,
                          "placement": "first-fit ascending node_name", "horizon_seconds": 7_776_000},
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "runtime_seconds_total": time.perf_counter() - run_started,
        "peak_rss_kib_process": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "results": results,
        "outputs": {p.name: sha256(p) for p in args.out.iterdir() if p.is_file()},
    }
    write_json(args.out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
