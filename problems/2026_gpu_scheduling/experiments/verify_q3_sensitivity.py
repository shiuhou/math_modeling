#!/usr/bin/env python3
"""Independently replay and verify every persisted Q3-S2 scenario."""
import argparse
import hashlib
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
from gpu_scheduling.q3 import Config, POLICIES, SOURCE, TARGET, route
from gpu_scheduling.q3_validation import require, verify_metrics, verify_schedule


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(native(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def timing(frame, horizon):
    if frame.empty:
        return {"jobs": 0}
    wait = frame.start - frame.submit_time
    jct = frame.finish - frame.submit_time
    relative = frame.finish - frame.submit_time - frame.original_duration
    return {
        "jobs": len(frame), "completed_at_horizon": int((frame.finish <= horizon).sum()),
        "mean_wait_hours": wait.mean() / 3600, "p95_wait_hours": wait.quantile(.95) / 3600,
        "p99_wait_hours": wait.quantile(.99) / 3600, "max_wait_hours": wait.max() / 3600,
        "mean_jct_hours": jct.mean() / 3600, "mean_relative_completion_delay_hours": relative.mean() / 3600,
    }


def paired_check(base, treatment, model, horizon, report):
    b = base.set_index("job_name").sort_index()
    t = treatment.set_index("job_name").sort_index()
    require(b.index.equals(t.index), "paired original IDs")
    x = b if model is None else b[b.original_gpu_model == model]
    y = t.loc[x.index]
    dw = y.start - x.start
    df = y.finish - x.finish
    expected = {
        "jobs": len(x), "mean_delta_wait_hours": dw.mean() / 3600,
        "p95_delta_wait_hours": dw.quantile(.95) / 3600, "p99_delta_wait_hours": dw.quantile(.99) / 3600,
        "max_delta_wait_hours": dw.max() / 3600, "positive_extra_wait_hours": dw.clip(lower=0).sum() / 3600,
        "zero_wait_new_delay_jobs": int(((x.start == x.submit_time) & (y.start > y.submit_time)).sum()),
        "waiting_worse_jobs": int((dw > 0).sum()), "waiting_better_jobs": int((dw < 0).sum()),
        "equal_wait_jobs": int((dw == 0).sum()), "mean_delta_finish_hours": df.mean() / 3600,
        "p95_delta_finish_hours": df.quantile(.95) / 3600, "max_delta_finish_hours": df.max() / 3600,
        "finish_improved_jobs": int((df < 0).sum()), "finish_worsened_jobs": int((df > 0).sum()),
        "finish_equal_jobs": int((df == 0).sum()), "positive_completion_delay_hours": df.clip(lower=0).sum() / 3600,
        "completion_count_delta_at_horizon": int((y.finish <= horizon).sum() - (x.finish <= horizon).sum()),
    }
    require(set(report) == set(expected), "paired metric keys")
    for key, value in expected.items():
        require(np.isclose(float(report[key]), float(value), rtol=1e-11, atol=1e-10), "paired metric " + key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PROBLEM / "data/raw")
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--s0", type=Path, default=REPO / "outputs/b-q3-fixed-split-v1-final")
    args = parser.parse_args()
    started = time.perf_counter()
    nodes, jobs, data_hashes = read_data(args.data)
    manifest = json.loads((args.run / "manifest.json").read_text())
    require(manifest["status"] == "PASS", "sensitivity run status")
    require(manifest["data_sha256"] == data_hashes, "raw data hash")
    require(manifest["jobs"] == len(jobs), "full original job count")
    s0manifest = json.loads((args.s0 / "run.json").read_text())
    require(s0manifest["status"] == "PASS", "S0 status")
    s0 = {p: {x: pd.read_csv(args.s0 / f"{p}_{x}_jobs.csv.gz") for x in ("M0", "M1")} for p in POLICIES}
    checks = {}
    route_sets = {}
    for scenario, raw_config in manifest["scenarios"].items():
        config = Config(**raw_config)
        for policy in POLICIES:
            label = f"{scenario}_{policy}"
            job_path = args.run.parent.parent / "outputs" / "q3-s2-placeholder"
            # The manifest records the explicit output root; resolve it from the
            # runner's command-independent relative directory when possible.
            output_root = Path(manifest["output_root"])
            if not output_root.is_absolute():
                output_root = REPO / output_root
            scenario_dir = output_root / label
            frame = pd.read_csv(scenario_dir / "jobs.csv.gz")
            ledger = pd.read_csv(scenario_dir / "placements.csv.gz")
            report = json.loads((args.run / f"{label}_metrics.json").read_text())
            require(report["configuration"] == raw_config, label + " configuration")
            schedule = verify_schedule(nodes, jobs, frame, ledger, config)
            require(verify_metrics(nodes, frame, config, report["q3_describe"])["status"] == "PASS", label + " metrics")
            require(frame.finish.eq(frame.start + frame.duration).all(), label + " finish identity")
            require((frame.duration > 0).all() and np.issubdtype(frame.duration.dtype, np.integer), label + " integer duration")
            route_sets[label] = set(frame.loc[frame.route_reason == "routed", "job_name"].astype(int))
            paired_check(s0[policy]["M0"], frame, SOURCE, config.horizon_seconds, report["paired_M0"]["A10"])
            paired_check(s0[policy]["M0"], frame, TARGET, config.horizon_seconds, report["paired_M0"]["native_A100"])
            paired_check(s0[policy]["M0"], frame, None, config.horizon_seconds, report["paired_M0"]["ALL"])
            paired_check(s0[policy]["M1"], frame, SOURCE, config.horizon_seconds, report["paired_S0"]["A10"])
            paired_check(s0[policy]["M1"], frame, TARGET, config.horizon_seconds, report["paired_S0"]["native_A100"])
            paired_check(s0[policy]["M1"], frame, None, config.horizon_seconds, report["paired_S0"]["ALL"])
            checks[label] = {"status": "PASS", "schedule": schedule, "metrics": "PASS", "paired": "PASS"}
            print(label + ": raw routing, physical replay, metrics and paired comparisons PASS", flush=True)
    # Routing is policy-independent; check the explicit subsets from persisted data.
    for policy in POLICIES:
        s1, s2 = route_sets[f"S1_{policy}"], route_sets[f"S2_{policy}"]
        # S1 is 5%, S2 is 20%; S0 is 10% and is represented by persisted S0.
        s0_ids = set(s0[policy]["M1"].loc[s0[policy]["M1"].route_reason == "routed", "job_name"].astype(int))
        require(s1 <= s0_ids <= s2, "nested 5/10/20 routing sets")
        require(route_sets[f"S5_{policy}"] == s0_ids, "sigma=2 routed set changed")
    target = nodes[nodes.gpu_model == TARGET].sort_values("node_name")
    require(set(target.head(30).node_name) < set(target.head(60).node_name) < set(target.head(90).node_name), "donor node prefixes")
    # Sigma=2 is a duration-only change for routed jobs; native and unrouted rows retain S0 duration.
    for policy in POLICIES:
        s0f = s0[policy]["M1"].set_index("job_name").sort_index()
        s5f = pd.read_csv((Path(manifest["output_root"]) if Path(manifest["output_root"]).is_absolute() else REPO / manifest["output_root"]) / f"S5_{policy}" / "jobs.csv.gz").set_index("job_name").sort_index()
        routed = s0f.route_reason == "routed"
        require((s5f.loc[routed, "duration"] == 2 * s0f.loc[routed, "original_duration"]).all(), "sigma=2 routed durations")
        require((s5f.loc[~routed, "duration"] == s0f.loc[~routed, "duration"]).all(), "sigma=2 non-routed durations")
    result = {"status": "PASS", "checks": checks, "routing_subset": "PASS", "donor_prefixes": "PASS", "sigma_semantics": "PASS", "seconds": time.perf_counter() - started}
    write_json(args.run / "independent_verification.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
