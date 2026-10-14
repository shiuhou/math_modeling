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
import numpy as np
import os

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


class PhaseLog:
    """Durable, sparse diagnostics; never added to scheduling evidence."""
    def __init__(self, path: Path):
        self.path = path
        self.started = time.perf_counter()
        self.policy = None

    def __call__(self, phase, action, **counts):
        rss = None
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                rss = int(line.split()[1])
                break
        row = {"elapsed_seconds": time.perf_counter() - self.started,
               "policy": self.policy, "phase": phase, "action": action,
               "rss_kib": rss,
               "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               **counts}
        # Phase boundaries and one sample per 4096 epochs/events only.
        # Flush+fsync means SIGKILL cannot discard the last complete record.
        with self.path.open("a") as handle:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def duration_strata(jobs, starts, ends, horizon: int) -> dict:
    """Report fixed rank-based duration strata for cross-policy comparison."""
    durations = jobs.duration.to_numpy(dtype="int64")
    waits = starts - jobs.submit_time.to_numpy(dtype="int64")
    bounds = np.quantile(durations, [0.0, 0.5, 0.9, 0.99, 1.0], method="linear")
    labels = ("q00_q50", "q50_q90", "q90_q99", "q99_q100")
    out = {}
    for i, label in enumerate(labels):
        lo, hi = bounds[i], bounds[i + 1]
        mask = (durations >= lo) & ((durations <= hi) if i == len(labels) - 1 else (durations < hi))
        if not mask.any():
            out[label] = {"count": 0, "duration_min_seconds": None,
                          "duration_max_seconds": None, "mean_wait_hours": None,
                          "p95_wait_hours": None, "zero_wait_fraction": None}
            continue
        group_wait = waits[mask]
        out[label] = {
            "count": int(mask.sum()),
            "duration_min_seconds": int(durations[mask].min()),
            "duration_max_seconds": int(durations[mask].max()),
            "mean_wait_hours": float(group_wait.mean() / 3600),
            "p95_wait_hours": float(np.quantile(group_wait, 0.95) / 3600),
            "zero_wait_fraction": float(np.mean(group_wait == 0)),
        }
    return {"quantile_bounds_seconds": [float(x) for x in bounds], "bands": out}


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
    phase = PhaseLog(args.out / "phase_log.jsonl")
    for requested in args.policies:
        phase.policy = requested
        phase("simulate_pool", "begin", jobs=len(jobs), nodes=len(pool))
        policy_started = time.perf_counter()
        scheduler_started = time.perf_counter()
        result = simulate_pool(pool, jobs, requested, theta_seconds=args.theta_seconds,
                               reservation_k=args.reservation_k, event_mode=args.event_mode, progress=phase)
        scheduler_seconds = time.perf_counter() - scheduler_started
        phase("simulate_pool", "end", jobs=len(jobs), events=len(result["events"]), promises=len(result["reservations"]))
        validation_started = time.perf_counter()
        validate_reservations(pool, result["jobs"], result, progress=phase)
        validation_seconds = time.perf_counter() - validation_started
        phase("metrics", "begin")
        metrics_started = time.perf_counter()
        metric_values = metrics(result, pool, 7_776_000)
        metric_values["duration_strata"] = duration_strata(
            result["jobs"], result["starts"], result["ends"], 7_776_000)
        metrics_seconds = time.perf_counter() - metrics_started
        phase("metrics", "end")
        phase("persistence", "begin")
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
            "reservation_evidence_schema_version": result["reservation_evidence_schema_version"],
            "reservations": result["reservations"], "events": result["events"], "cost": result["cost"]})
        phase("persistence", "end", files=3)
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
