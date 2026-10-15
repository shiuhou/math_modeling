#!/usr/bin/env python3
"""Run the predeclared Q3-S2 fixed-split single-factor sensitivity study.

This runner deliberately reuses the v1 ``q3.simulate`` and the persisted,
verified S0 schedules.  It does not regenerate M0/S0 and it never searches
over parameters.  Large job and placement tables are written below
``--output-root``; the small, reviewable manifest and metrics stay below
``--out``.
"""
from dataclasses import asdict
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time

import numpy as np
import pandas as pd

PROBLEM = Path(__file__).resolve().parents[1]
REPO = PROBLEM.parents[1]
sys.path.insert(0, str(PROBLEM / "src"))

from gpu_scheduling.data import native, read_data
from gpu_scheduling.q3 import Config, POLICIES, SOURCE, TARGET, describe, route, selected, simulate

HORIZON = 7_776_000
S0_CONFIG = Config(60, 1, 10, True, 1, HORIZON, "q3-fixed-split-v1")
SCENARIOS = {
    "S1": Config(60, 1, 20, True, 1, HORIZON, "q3-fixed-split-v1"),
    "S2": Config(60, 1, 5, True, 1, HORIZON, "q3-fixed-split-v1"),
    "S3": Config(30, 1, 10, True, 1, HORIZON, "q3-fixed-split-v1"),
    "S4": Config(90, 1, 10, True, 1, HORIZON, "q3-fixed-split-v1"),
    "S5": Config(60, 1, 10, True, 2, HORIZON, "q3-fixed-split-v1"),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(native(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def sha_text(values):
    return hashlib.sha256("\n".join(str(int(v)) for v in sorted(values)).encode()).hexdigest()


def timing(frame, horizon):
    if frame.empty:
        return {"jobs": 0}
    wait = frame.start - frame.submit_time
    jct = frame.finish - frame.submit_time
    relative = frame.finish - frame.submit_time - frame.original_duration
    out = {
        "jobs": int(len(frame)),
        "completed_at_horizon": int((frame.finish <= horizon).sum()),
        "mean_wait_hours": float(wait.mean() / 3600),
        "p95_wait_hours": float(wait.quantile(.95) / 3600),
        "p99_wait_hours": float(wait.quantile(.99) / 3600),
        "max_wait_hours": float(wait.max() / 3600),
        "mean_jct_hours": float(jct.mean() / 3600),
        "p95_jct_hours": float(jct.quantile(.95) / 3600),
        "p99_jct_hours": float(jct.quantile(.99) / 3600),
        "max_jct_hours": float(jct.max() / 3600),
        "mean_relative_completion_delay_hours": float(relative.mean() / 3600),
        "p95_relative_completion_delay_hours": float(relative.quantile(.95) / 3600),
    }
    return out


def paired(base, treatment, mask, horizon):
    order = base.set_index("job_name").sort_index()
    mask = pd.Series(mask, index=base.job_name).reindex(order.index).to_numpy()
    b = order
    t = treatment.set_index("job_name").sort_index()
    if not b.index.equals(t.index):
        raise AssertionError("paired schedules have different original ID sets")
    x, y = b[mask], t.loc[b.index[mask]]
    dw = y.start - x.start
    df = y.finish - x.finish
    return {
        "jobs": int(len(x)),
        "mean_delta_wait_hours": float(dw.mean() / 3600),
        "p95_delta_wait_hours": float(dw.quantile(.95) / 3600),
        "p99_delta_wait_hours": float(dw.quantile(.99) / 3600),
        "max_delta_wait_hours": float(dw.max() / 3600),
        "positive_extra_wait_hours": float(dw.clip(lower=0).sum() / 3600),
        "zero_wait_new_delay_jobs": int(((x.start == x.submit_time) & (y.start > y.submit_time)).sum()),
        "waiting_worse_jobs": int((dw > 0).sum()),
        "waiting_better_jobs": int((dw < 0).sum()),
        "equal_wait_jobs": int((dw == 0).sum()),
        "mean_delta_finish_hours": float(df.mean() / 3600),
        "p95_delta_finish_hours": float(df.quantile(.95) / 3600),
        "max_delta_finish_hours": float(df.max() / 3600),
        "finish_improved_jobs": int((df < 0).sum()),
        "finish_worsened_jobs": int((df > 0).sum()),
        "finish_equal_jobs": int((df == 0).sum()),
        "positive_completion_delay_hours": float(df.clip(lower=0).sum() / 3600),
        "completion_count_delta_at_horizon": int((y.finish <= horizon).sum() - (x.finish <= horizon).sum()),
    }


def cohort_metrics(nodes, frame, s0, m0, config):
    a10 = frame.original_gpu_model == SOURCE
    a100 = frame.original_gpu_model == TARGET
    all_mask = np.ones(len(frame), dtype=bool)
    out = {
        "A10": timing(frame[a10], config.horizon_seconds),
        "native_A100": timing(frame[a100], config.horizon_seconds),
        "ALL": timing(frame[all_mask], config.horizon_seconds),
        "routed_A10": timing(frame[frame.route_reason == "routed"], config.horizon_seconds),
        "unrouted_A10": timing(frame[a10 & (frame.route_reason != "routed")], config.horizon_seconds),
        "physical": describe(nodes, frame, config)["physical"],
        "routing": {
            "counts": {str(k): int(v) for k, v in frame.route_reason.value_counts().items()},
            "routed_jobs": int((frame.route_reason == "routed").sum()),
            "routed_gpu_work": float((frame.loc[frame.route_reason == "routed", "original_duration"] * frame.loc[frame.route_reason == "routed", "worker_num"] * frame.loc[frame.route_reason == "routed", "gpu_request"]).sum()),
            "all_A10_gpu_work": float((frame.loc[a10, "original_duration"] * frame.loc[a10, "worker_num"] * frame.loc[a10, "gpu_request"]).sum()),
        },
    }
    out["q3_describe"] = describe(nodes, frame, config)
    out["routing"]["routed_gpu_work_fraction"] = out["routing"]["routed_gpu_work"] / out["routing"]["all_A10_gpu_work"]
    out["paired_M0"] = {
        "A10": paired(m0, frame, m0.original_gpu_model.to_numpy() == SOURCE, config.horizon_seconds),
        "native_A100": paired(m0, frame, m0.original_gpu_model.to_numpy() == TARGET, config.horizon_seconds),
        "ALL": paired(m0, frame, np.ones(len(m0), dtype=bool), config.horizon_seconds),
    }
    out["paired_S0"] = {
        "A10": paired(s0, frame, s0.original_gpu_model.to_numpy() == SOURCE, config.horizon_seconds),
        "native_A100": paired(s0, frame, s0.original_gpu_model.to_numpy() == TARGET, config.horizon_seconds),
        "ALL": paired(s0, frame, np.ones(len(s0), dtype=bool), config.horizon_seconds),
    }
    return out


def protected_source_hashes(s0_manifest):
    current = {}
    for rel, expected in s0_manifest["source_sha256"].items():
        path = REPO / rel
        if not path.exists() or digest(path) != expected:
            raise RuntimeError(f"S0 source snapshot mismatch: {rel}")
        current[rel] = expected
    return current


def load_s0(path):
    manifest = json.loads((path / "run.json").read_text())
    if manifest["configuration"] != asdict(S0_CONFIG):
        raise RuntimeError("S0 configuration does not match frozen sensitivity protocol")
    protected_source_hashes(manifest)
    data_hashes = manifest["data_sha256"]
    frames = {}; metrics = json.loads((path / "metrics.json").read_text())
    for policy in POLICIES:
        frames[policy] = {}
        for label in ("M0", "M1"):
            frames[policy][label] = pd.read_csv(path / f"{policy}_{label}_jobs.csv.gz")
    return {"manifest": manifest, "frames": frames, "metrics": metrics, "data_sha256": data_hashes}


def routing_audit(nodes, jobs):
    routed = {}
    for name, config in [("S0", S0_CONFIG), *SCENARIOS.items()]:
        _, frame = route(nodes, jobs, config)
        routed[name] = set(frame.loc[frame.route_reason == "routed", "job_name"].astype(int))
    if not (routed["S1"] <= routed["S0"] <= routed["S2"]):
        raise AssertionError("fixed hash routing is not 5% subset 10% subset 20%")
    if routed["S5"] != routed["S0"]:
        raise AssertionError("sigma=2 changed the S0 routed ID set")
    target = nodes[nodes.gpu_model == TARGET].sort_values("node_name")
    node_sets = {str(n): list(target.head(n).node_name.astype(int)) for n in (30, 60, 90)}
    if not (set(node_sets["30"]) < set(node_sets["60"]) < set(node_sets["90"])):
        raise AssertionError("donor prefixes are not nested")
    return {
        "routed_job_counts": {k: len(v) for k, v in routed.items()},
        "nested_routing": {"S1_subset_S0": True, "S0_subset_S2": True, "S5_equals_S0": True},
        "donor_node_counts": {k: len(v) for k, v in node_sets.items()},
        "donor_node_prefix_sha256": {k: sha_text(v) for k, v in node_sets.items()},
        "donor_prefix_nested": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PROBLEM / "data/raw")
    parser.add_argument("--s0", type=Path, default=REPO / "outputs/b-q3-fixed-split-v1-final")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.output_root.exists():
        parser.error("choose new result and output directories")
    started = time.perf_counter()
    nodes, jobs, data_hashes = read_data(args.data)
    s0 = load_s0(args.s0)
    if s0["data_sha256"] != data_hashes:
        raise RuntimeError("S0 data hashes do not match current raw data")
    routing = routing_audit(nodes, jobs)
    args.out.mkdir(parents=True); args.output_root.mkdir(parents=True)
    write_json(args.out / "frozen_scenarios.json", {"S0": asdict(S0_CONFIG), **{k: asdict(v) for k, v in SCENARIOS.items()}})
    write_json(args.out / "routing_audit.json", routing)
    status = {}; details = {}
    for scenario, config in SCENARIOS.items():
        details[scenario] = {}
        for policy in POLICIES:
            label = f"{scenario}_{policy}"
            scenario_dir = args.output_root / label
            scenario_dir.mkdir(parents=True)
            tick = time.perf_counter()
            frame, ledger = simulate(nodes, jobs, policy, config)
            frame.to_csv(scenario_dir / "jobs.csv.gz", index=False, compression="gzip")
            ledger.to_csv(scenario_dir / "placements.csv.gz", index=False, compression="gzip")
            base_s0 = s0["frames"][policy]["M1"]
            base_m0 = s0["frames"][policy]["M0"]
            metrics = cohort_metrics(nodes, frame, base_s0, base_m0, config)
            metrics["scenario"] = scenario; metrics["policy"] = policy; metrics["configuration"] = asdict(config)
            metrics["wall_seconds"] = time.perf_counter() - tick
            metrics["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            write_json(args.out / f"{label}_metrics.json", metrics)
            details[scenario][policy] = {"status": "PASS", "wall_seconds": metrics["wall_seconds"], "peak_rss_mb": metrics["peak_rss_mb"], "output": str(scenario_dir)}
            print(f"{label}: simulated in {metrics['wall_seconds']:.2f}s", flush=True)
    status = {s: {p: {"status": "PASS", **details[s][p]} for p in POLICIES} for s in SCENARIOS}
    write_json(args.out / "scenario_status.json", status)
    write_json(args.out / "sensitivity_metrics.json", {s: {p: json.loads((args.out / f"{s}_{p}_metrics.json").read_text()) for p in POLICIES} for s in SCENARIOS})
    manifest = {
        "schema_version": 1, "kind": "q3_fixed_split_sensitivity_v1", "status": "PASS",
        "base_commit": s0["manifest"]["git_commit"], "current_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "current_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip()),
        "data_sha256": data_hashes, "jobs": len(jobs), "nodes": len(nodes), "horizon_seconds": HORIZON,
        "s0_artifact": str(args.s0), "s0_manifest_sha256": digest(args.s0 / "run.json"),
        "s0_source_sha256": s0["manifest"]["source_sha256"], "routing_audit": routing,
        "scenarios": {k: asdict(v) for k, v in SCENARIOS.items()}, "policies": list(POLICIES),
        "assumptions": {"compatibility": "scenario assumption", "sigma": "not hardware benchmark", "no_parameter_search": True},
        "cost": {"wall_seconds": time.perf_counter() - started, "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, "one_policy_at_a_time": True},
        "output_root": str(args.output_root),
        "command": sys.argv, "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "platform": platform.platform()},
        "sensitivity_decision": "GO only after independent verification; no exact break-even sigma claimed",
    }
    write_json(args.out / "manifest.json", manifest)


if __name__ == "__main__":
    main()
