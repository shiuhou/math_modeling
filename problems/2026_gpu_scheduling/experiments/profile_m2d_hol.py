#!/usr/bin/env python3
"""Bounded cProfile probe for the protected-head SPT urgent-HOL path."""
from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import time
from pathlib import Path

import pandas as pd

from gpu_scheduling.data import prepare_data
from gpu_scheduling.simulator import simulate_pool


def fixture(count: int):
    nodes = pd.DataFrame({"node_name": [0, 1], "gpu_model": ["X", "X"],
                          "gpu_capacity_num": [1, 1], "cpu_num": [1, 1]})
    rows = [
        {"job_name": 0, "gpu_model": "X", "gpu_request": 1, "cpu_request": 0.0,
         "worker_num": 1, "submit_time": 0, "duration": 100},
        {"job_name": 1, "gpu_model": "X", "gpu_request": 1, "cpu_request": 0.0,
         "worker_num": 2, "submit_time": 0, "duration": 200},
    ]
    rows.extend({"job_name": j, "gpu_model": "X", "gpu_request": 1,
                 "cpu_request": 0.0, "worker_num": 2, "submit_time": j,
                 "duration": 5} for j in range(2, count))
    return prepare_data(nodes, pd.DataFrame(rows))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=2002)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.jobs < 3 or args.out.exists():
        parser.error("jobs must be >=3 and output must be new")
    nodes, jobs = fixture(args.jobs)
    profile = cProfile.Profile()
    started = time.perf_counter()
    profile.enable()
    result = simulate_pool(nodes, jobs, "SPT-URGENT-HOL", theta_seconds=1,
                           reservation_k=200, event_mode="shared-timer")
    profile.disable()
    elapsed = time.perf_counter() - started
    schedule = {"starts": result["starts"].tolist(), "ends": result["ends"].tolist(),
                "plans": result["plans"]}
    stats = io.StringIO()
    pstats.Stats(profile, stream=stats).sort_stats("cumtime").print_stats(15)
    output = {
        "schema_version": 1, "kind": "m2d_protected_hol_profile",
        "jobs": args.jobs, "theta_seconds": 1, "reservation_k": 200,
        "event_mode": "shared-timer", "elapsed_seconds": elapsed,
        "reservations": len(result["reservations"]), "event_count": len(result["events"]),
        "cost": result["cost"],
        "schedule_sha256": hashlib.sha256(json.dumps(schedule, sort_keys=True).encode()).hexdigest(),
        "events_sha256": hashlib.sha256(json.dumps(result["events"], sort_keys=True).encode()).hexdigest(),
        "profile_top15": stats.getvalue(),
    }
    args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
