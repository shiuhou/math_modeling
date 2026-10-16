#!/usr/bin/env python3
"""Run the frozen GS1 placement matrix and persist paired replay evidence."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROBLEM = Path(__file__).resolve().parents[1]
REPO = PROBLEM.parents[1]
sys.path.insert(0, str(PROBLEM / "src"))
from gpu_scheduling.data import read_data, native  # noqa: E402
from gpu_scheduling.evaluation import metrics  # noqa: E402
from gpu_scheduling.simulator import simulate_pool  # noqa: E402


def dump(path, value):
    path.write_text(json.dumps(native(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def order_for(pool, seed):
    if seed is None:
        return None
    return np.random.default_rng(int(seed)).permutation(len(pool)).astype(int).tolist()


def run_one(pool, jobs, policy, placement, seed, theta, out, horizon):
    order = order_for(pool, seed)
    started = time.perf_counter()
    result = simulate_pool(pool, jobs, policy, theta_seconds=theta,
                           reservation_k=200, event_mode="shared-timer",
                           placement=placement, node_order=order)
    elapsed = time.perf_counter() - started
    name = f"{policy.lower()}-{placement}-seed{seed if seed is not None else 'id'}"
    frame = result["jobs"][["job_name", "gpu_model", "gpu_request", "cpu_units", "worker_num", "submit_time", "duration"]].copy()
    frame["start"] = result["starts"]
    frame["finish"] = result["ends"]
    frame["wait"] = frame.start - frame.submit_time
    frame.to_csv(out / f"{name}-job-times.csv.gz", index=False, compression="gzip")
    with gzip.open(out / f"{name}-placements.csv.gz", "wt", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["job_name", "node_name", "workers"])
        for jid, plan in zip(result["jobs"].job_name, result["plans"]):
            writer.writerows((int(jid), int(pool.node_name.iloc[m]), int(w)) for m, w in plan)
    summary = metrics(result, pool, horizon)
    summary.update({"policy": policy, "placement": placement, "seed": seed,
                    "node_order": result["node_order"], "runtime_seconds": elapsed,
                    "cost": result["cost"], "jobs": int(len(frame))})
    dump(out / f"{name}-summary.json", summary)
    return name, frame, summary


def pair_summary(a, b, policy, out):
    joined = a[["job_name", "wait", "start", "finish"]].merge(
        b[["job_name", "wait", "start", "finish"]], on="job_name", suffixes=("_ff", "_ratio"))
    delta = joined.wait_ratio - joined.wait_ff
    record = {"policy": policy, "jobs": len(joined),
              "mean_wait_delta_hours": float(delta.mean() / 3600),
              "p95_wait_delta_hours": float(delta.quantile(.95) / 3600),
              "positive_added_wait_total_hours": float(delta.clip(lower=0).sum() / 3600),
              "improved_jobs": int((delta < 0).sum()), "worsened_jobs": int((delta > 0).sum()),
              "unchanged_jobs": int((delta == 0).sum()),
              "max_improvement_hours": float(-delta.min() / 3600),
              "max_regression_hours": float(delta.max() / 3600)}
    dump(out / f"paired-{policy.lower()}-ff-vs-ratio.json", record)
    # Persist job-level strata so a pooled mean cannot hide a shape-specific
    # regression.  Bins are descriptive, not tuned thresholds.
    base = a[["job_name", "cpu_units", "gpu_request", "worker_num"]]
    joined = joined.merge(base, on="job_name", how="left")
    joined["cpu_gpu_ratio"] = joined.cpu_units / joined.gpu_request
    joined["cpu_gpu_ratio_bin"] = pd.cut(joined.cpu_gpu_ratio, [-1, 0, 100, 400, 10**9],
                                          labels=["0", "(0,100]", "(100,400]", ">400"])
    strata = []
    for column in ("cpu_gpu_ratio_bin", "worker_num", "gpu_request"):
        for key, sub in joined.groupby(column, observed=True):
            d = sub.wait_ratio - sub.wait_ff
            strata.append({"dimension": column, "level": str(key), "jobs": len(sub),
                           "mean_wait_delta_hours": float(d.mean() / 3600),
                           "improved_jobs": int((d < 0).sum()), "worsened_jobs": int((d > 0).sum()),
                           "positive_added_wait_total_hours": float(d.clip(lower=0).sum() / 3600)})
    dump(out / f"paired-{policy.lower()}-strata.json", strata)
    return record


def replay_ledger(pool, jobs, times_path, placements_path):
    """Replay persisted timing/placement files without using simulator plans."""
    times = pd.read_csv(times_path)
    ledger = pd.read_csv(placements_path)
    expected = set(int(x) for x in jobs.job_name)
    if set(times.job_name) != expected or set(ledger.job_name) != expected:
        return {"status": "FAIL", "reason": "incomplete job IDs"}
    plans = {int(j): [(int(node), int(w)) for _, node, w in g.itertuples(index=False, name=None)]
             for j, g in ledger.groupby("job_name")}
    free_g = pool.gpu_capacity_num.to_numpy(dtype=np.int64).copy()
    free_c = pool.cpu_units.to_numpy(dtype=np.int64).copy()
    node_index = {int(name): i for i, name in enumerate(pool.node_name)}
    by_job = jobs.set_index("job_name")
    events = sorted([(int(r.finish), 0, int(r.job_name)) for r in times.itertuples()] +
                    [(int(r.start), 1, int(r.job_name)) for r in times.itertuples()])
    for t, kind, jid in events:
        row = by_job.loc[jid]
        q, c = int(row.gpu_request), int(row.cpu_units)
        entries = plans[jid]
        if kind == 0:
            for node, w in entries:
                i = node_index[int(node)]
                free_g[i] += int(w) * q
                free_c[i] += int(w) * c
        else:
            if sum(int(w) for _, w in entries) != int(row.worker_num):
                return {"status": "FAIL", "reason": f"worker count {jid}"}
            for node, w in entries:
                i = node_index[int(node)]
                if int(w) * q > int(free_g[i]) or int(w) * c > int(free_c[i]):
                    return {"status": "FAIL", "reason": f"capacity {jid}"}
            for node, w in entries:
                i = node_index[int(node)]
                free_g[i] -= int(w) * q
                free_c[i] -= int(w) * c
    ok = np.array_equal(free_g, pool.gpu_capacity_num.to_numpy(dtype=np.int64)) and np.array_equal(free_c, pool.cpu_units.to_numpy(dtype=np.int64))
    return {"status": "PASS" if ok else "FAIL", "final_gpu": free_g.tolist(), "final_cpu": free_c.tolist()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=PROBLEM / "data/raw")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--theta-seconds", type=int, default=604800)
    ap.add_argument("--horizon-seconds", type=int)
    args = ap.parse_args()
    if args.out.exists():
        ap.error("output exists; choose a new directory")
    nodes, jobs, hashes = read_data(args.data)
    pool = nodes[nodes.gpu_model == "GPU-series-1"].sort_values("node_name").reset_index(drop=True)
    frame = jobs[jobs.gpu_model == "GPU-series-1"].sort_values(["submit_time", "job_name"]).reset_index(drop=True)
    if pool.empty or frame.empty:
        ap.error("raw data has no complete GPU-series-1 pool")
    horizon = int(frame.submit_time.max()) if args.horizon_seconds is None else int(args.horizon_seconds)
    args.out.mkdir(parents=True)
    dump(args.out / "manifest.json", {
        "schema_version": 1, "kind": "gs1_placement_matrix", "base": "2026-mcm-b-baseline-v1",
        "gpu_model": "GPU-series-1", "jobs": len(frame), "nodes": len(pool),
        "data_sha256": hashes, "configuration": {"theta_seconds": args.theta_seconds,
        "event_mode": "shared-timer", "horizon_seconds": horizon,
        "initial_state": "all nodes idle", "completion": "full drain",
        "main_matrix": ["FCFS-HOL/ff-id", "FCFS-HOL/ratio", "SPT-HOL/ff-id", "SPT-HOL/ratio"],
        "ff_sensitivity": [17, 29]},
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "code_commit": __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()})
    runs = {}
    for policy in ("FCFS-HOL", "SPT-HOL"):
        for placement in ("ff-id", "ratio"):
            name, times, summary = run_one(pool, frame, policy, placement, None,
                                           args.theta_seconds, args.out, horizon)
            runs[name] = summary
        # Paired placement differences use identical policy and trace.
        ff = pd.read_csv(args.out / f"{policy.lower()}-ff-id-seedid-job-times.csv.gz")
        ratio = pd.read_csv(args.out / f"{policy.lower()}-ratio-seedid-job-times.csv.gz")
        pair_summary(ff, ratio, policy, args.out)
    for seed in (17, 29):
        for policy in ("FCFS-HOL", "SPT-HOL"):
            name, _, summary = run_one(pool, frame, policy, "ff-id", seed,
                                       args.theta_seconds, args.out, horizon)
            runs[name] = summary
    replay = {}
    for path in sorted(args.out.glob("*-job-times.csv.gz")):
        stem = path.name[:-len("-job-times.csv.gz")]
        replay[stem] = replay_ledger(pool, frame, path, args.out / f"{stem}-placements.csv.gz")
    dump(args.out / "independent_replay.json", {"status": "PASS" if all(x["status"] == "PASS" for x in replay.values()) else "FAIL", "runs": replay})
    dump(args.out / "matrix_summary.json", {"runs": runs,
          "all_runs_completed": len(runs) == 8,
          "independent_replay": "PASS" if all(x["status"] == "PASS" for x in replay.values()) else "FAIL",
          "status": "PASS" if len(runs) == 8 and all(x["status"] == "PASS" for x in replay.values()) else "FAIL"})
    print(f"Wrote {len(runs)} GS1 placement runs to {args.out}")


if __name__ == "__main__":
    main()
