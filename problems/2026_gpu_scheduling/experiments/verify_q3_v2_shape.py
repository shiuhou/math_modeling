#!/usr/bin/env python3
"""Independent replay of persisted Q3-V2 R-shape schedules."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

PROBLEM = Path(__file__).resolve().parents[1]
REPO = PROBLEM.parents[1]
sys.path.insert(0, str(PROBLEM / "src"))

from gpu_scheduling.data import native, read_data
from gpu_scheduling.q3 import Config, POLICIES, SOURCE, TARGET
from gpu_scheduling.q3_v2 import derive_shape_limit, route_shape
from gpu_scheduling.validation import validate


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def timing(frame, horizon):
    wait = frame.start - frame.submit_time
    jct = frame.finish - frame.submit_time
    return {
        "jobs": len(frame),
        "completed_at_horizon": int((frame.finish <= horizon).sum()),
        "mean_wait_hours": wait.mean() / 3600,
        "p95_wait_hours": wait.quantile(.95) / 3600,
        "p99_wait_hours": wait.quantile(.99) / 3600,
        "max_wait_hours": wait.max() / 3600,
        "mean_jct_hours": jct.mean() / 3600,
        "p95_jct_hours": jct.quantile(.95) / 3600,
        "p99_jct_hours": jct.quantile(.99) / 3600,
        "max_jct_hours": jct.max() / 3600,
        "mean_relative_completion_delay_hours": (jct - frame.original_duration).mean() / 3600,
        "p95_relative_completion_delay_hours": (jct - frame.original_duration).quantile(.95) / 3600,
    }


def verify_one(nodes, jobs, frame, ledger, config, report, expected_limit):
    raw = jobs.set_index("job_name").sort_index()
    saved = frame.set_index("job_name").sort_index()
    require(raw.index.equals(saved.index), "all original job IDs retained")
    for col in ["gpu_model", "cpu_request", "gpu_request", "worker_num", "submit_time", "duration"]:
        expected = saved["original_gpu_model"] if col == "gpu_model" else saved["original_duration"] if col == "duration" else raw[col]
        pd.testing.assert_series_equal(raw[col], expected, check_names=False, check_dtype=False)
    _, expected = route_shape(nodes, jobs, config)
    expected = expected.set_index("job_name").sort_index()
    for col in ["gpu_model", "duration", "partition", "route_reason"]:
        pd.testing.assert_series_equal(saved[col], expected[col], check_names=False, check_dtype=False)
    require(abs(float(report["shape"]["derived_cpu_per_gpu_limit"]) - expected_limit) < 1e-12, "shape threshold")
    require(not saved.index.duplicated().any(), "duplicate job IDs")
    require(not ledger.duplicated(["job_name", "node_name"]).any(), "duplicate placements")
    require(set(ledger.job_name) == set(saved.index), "every job has placement ledger rows")
    target = nodes[nodes.gpu_model == TARGET].sort_values("node_name")
    donor_ids = set(target.head(config.donor_nodes).node_name)
    plans = [[] for _ in range(len(saved))]
    ordered_nodes = nodes.sort_values("node_name").reset_index(drop=True)
    node_index = {int(v): i for i, v in enumerate(ordered_nodes.node_name)}
    job_index = {int(v): i for i, v in enumerate(saved.index)}
    for job, node, workers in ledger[["job_name", "node_name", "workers"]].itertuples(index=False, name=None):
        require(int(workers) > 0 and int(node) in node_index, "valid placement row")
        plans[job_index[int(job)]].append((node_index[int(node)], int(workers)))
        routed = saved.loc[int(job), "route_reason"] == "routed"
        require((int(node) in donor_ids) == routed, "foreign partition isolation")
    validate(ordered_nodes, saved.reset_index(), saved.start.to_numpy(), saved.finish.to_numpy(), plans)
    require(saved.finish.eq(saved.start + saved.duration).all(), "finish identity")
    for cohort, mask in {
        "A10": saved.original_gpu_model == SOURCE,
        "native_A100": saved.original_gpu_model == TARGET,
        "ALL": np.ones(len(saved), dtype=bool),
    }.items():
        expected_timing = timing(saved[mask], config.horizon_seconds)
        for key, value in expected_timing.items():
            require(np.isclose(float(report[cohort][key]), float(value), rtol=1e-11, atol=1e-10), cohort + " " + key)
    return {"status": "PASS", "jobs": len(saved), "routed_jobs": int((saved.route_reason == "routed").sum()), "physical_replay": "PASS", "route_replay": "PASS"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PROBLEM / "data/raw")
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    nodes, jobs, data_hashes = read_data(args.data)
    manifest = json.loads((args.run / "manifest.json").read_text())
    require(manifest["status"] == "PASS", "run status")
    require(manifest["data_sha256"] == data_hashes, "raw data hash")
    limit = derive_shape_limit(nodes, 60)
    checks = {}
    for scenario, raw in {"Rshape_sigma1": Config(60, 1, 10, True, 1, 7_776_000, "q3-fixed-split-v1"), "Rshape_sigma2": Config(60, 1, 10, True, 2, 7_776_000, "q3-fixed-split-v1")}.items():
        for policy in POLICIES:
            label = f"{scenario}_{policy}"
            frame = pd.read_csv(args.output_root / label / "jobs.csv.gz")
            ledger = pd.read_csv(args.output_root / label / "placements.csv.gz")
            report = json.loads((args.run / f"{label}_metrics.json").read_text())
            checks[label] = verify_one(nodes, jobs, frame, ledger, raw, report, limit)
            print(label + ": route, physical replay and metrics PASS", flush=True)
    result = {"status": "PASS", "checks": checks, "shape_threshold": limit, "seconds": time.perf_counter() - started}
    (args.run / "independent_verification.json").write_text(json.dumps(native(result), ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(native(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
