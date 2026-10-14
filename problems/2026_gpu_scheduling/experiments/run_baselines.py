#!/usr/bin/env python3
"""Run the sole FCFS/SJF-HOL DES and persist timings, node ledgers and metrics.

No experiment runs on import. --smoke uses the first 64 jobs of each GPU model;
its metrics are engineering checks, not full-trace performance claims.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

PROBLEM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROBLEM / "src"))
import numpy as np
import pandas as pd
from gpu_scheduling.audit import audit
from gpu_scheduling.data import native, read_data
from gpu_scheduling.evaluation import metrics
from gpu_scheduling.simulator import POLICY_ALIASES, simulate_pool


def write_json(path, value):
    path.write_text(json.dumps(native(value), ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--data", type=Path, default=PROBLEM / "data/raw", help="Raw CSV directory or original data ZIP")
    inputs.add_argument("--data-dir", type=Path, help=argparse.SUPPRESS)
    inputs.add_argument("--input-zip", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, required=True, help="New run directory; never overwritten")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--horizon-seconds", type=int, help="Default: last raw submission, occupancy [0,H)")
    parser.add_argument("--policies", nargs="+", choices=sorted(POLICY_ALIASES), default=["FCFS", "SJF-HOL"])
    parser.add_argument("--theta-seconds", type=int, default=4860000,
                        help="M1 timer threshold (default: 1350 hours)")
    parser.add_argument("--reservation-k", type=int, default=200,
                        help="Per-pool, per-timestamp candidate budget")
    args = parser.parse_args()
    if args.out.exists(): parser.error("Output exists; choose a new directory")
    if len(set(args.policies)) != len(args.policies): parser.error("Policies must not be repeated")
    started = time.perf_counter()
    nodes, raw_jobs, hashes = read_data(args.input_zip or args.data_dir or args.data)
    horizon = args.horizon_seconds if args.horizon_seconds is not None else int(raw_jobs.submit_time.max())
    if horizon <= 0: parser.error("Positive horizon required")
    accounting = audit(nodes, raw_jobs, hashes)
    jobs = raw_jobs.groupby("gpu_model", sort=False).head(64).copy() if args.smoke else raw_jobs
    args.out.mkdir(parents=True, exist_ok=False)
    repo = PROBLEM.parents[1]
    git = lambda *argv: subprocess.check_output(["git", *argv], cwd=repo, text=True).strip()
    code_files = sorted((PROBLEM / "src").rglob("*.py")) + [Path(__file__).resolve()]
    dirty = bool(git("status", "--porcelain"))
    code_hashes = {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in code_files}
    if dirty:
        for p in code_files:
            dest = args.out / "source" / p.relative_to(repo)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dest)
    record = {
        "schema_version": 1, "kind": "baseline_run", "scope": "smoke_first_64_per_model" if args.smoke else "full_trace",
        "code": {"commit": git("rev-parse", "HEAD"), "dirty": dirty, "sha256": code_hashes,
                 "snapshot": "source/" if dirty else None},
        "data_sha256": hashes, "raw_jobs": len(raw_jobs), "scheduled_jobs": len(jobs),
        "configuration": {"horizon_seconds": horizon, "policies": args.policies, "audit_only": args.audit_only,
                          "theta_seconds": args.theta_seconds, "reservation_k": args.reservation_k,
                          "cpu_scale": 100, "placement": "first-fit by ascending node_name",
                          "events": "all completions, then arrivals, then scheduling; half-open allocation intervals"},
        "command": ["python", str(Path(__file__).resolve().relative_to(repo)), *sys.argv[1:]],
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                        "platform": platform.platform()},
        "validation": {"data_accounting": "PASS", "capacity_replay": "NOT_RUN", "persisted_replay": "NOT_RUN"},
        "duration_seconds": None, "outputs": {},
    }
    write_json(args.out / "run.json", record)
    write_json(args.out / "data_audit.json", accounting)
    try:
        if not args.audit_only:
            rows = []
            for policy in args.policies:
                chunks = []
                with gzip.open(args.out / f"{policy}_node_placements.csv.gz", "wt", newline="", encoding="utf-8") as handle:
                    ledger = csv.writer(handle)
                    ledger.writerow(["job_name", "node_name", "workers"])
                    for model, sub in jobs.groupby("gpu_model", sort=True):
                        pool = nodes[nodes.gpu_model == model].sort_values("node_name").reset_index(drop=True)
                        result = simulate_pool(pool, sub, policy,
                                               theta_seconds=args.theta_seconds,
                                               reservation_k=args.reservation_k)
                        rows.append({"policy": policy, "gpu_model": model, **metrics(result, pool, horizon)})
                        for jid, plan in zip(result["jobs"].job_name, result["plans"]):
                            ledger.writerows((int(jid), int(pool.node_name.iloc[m]), w) for m, w in plan)
                        # Keep reservation/certificate evidence separate from the
                        # dense timing and allocation tables.
                        write_json(args.out / f"{policy}_{model}_reservations.json", {
                            "gpu_model": model, "policy": policy,
                            "reservations": result.get("reservations", []),
                            "events": result.get("events", []),
                            "cost": result.get("cost", {}),
                        })
                        frame = result["jobs"].drop(columns="cpu_units").copy()
                        frame["start"], frame["finish"] = result["starts"], result["ends"]
                        chunks.append(frame)
                        print(f"PASS {policy}/{model}: {len(frame)} jobs, independent node replay", flush=True)
                frame = pd.concat(chunks, ignore_index=True)
                frame.to_csv(args.out / f"{policy}_job_times.csv.gz", index=False, compression="gzip")
                combined = {"jobs": frame, "starts": frame.start.to_numpy(), "ends": frame.finish.to_numpy()}
                rows.append({"policy": policy, "gpu_model": "ALL", **metrics(combined, nodes, horizon)})
            write_json(args.out / "baseline_metrics.json", rows)
            record["validation"]["capacity_replay"] = "PASS"
    except Exception:
        record["validation"]["capacity_replay"] = "FAIL"
        raise
    finally:
        record["duration_seconds"] = time.perf_counter()-started
        record["outputs"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.out.iterdir() if p.is_file() and p.name != "run.json"}
        write_json(args.out / "run.json", record)
    print(f"Wrote {record['scope']} baseline outputs to {args.out}")


if __name__ == "__main__":
    main()
