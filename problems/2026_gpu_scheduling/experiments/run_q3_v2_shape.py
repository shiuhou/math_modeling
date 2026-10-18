#!/usr/bin/env python3
"""Run the bounded Q3-V2 R-shape candidate on the complete original trace.

The runner reuses persisted M0/S0/S5 schedules as fixed references and the
unchanged V1 pool DES.  It executes only four R-shape cases: FCFS/SJF-HOL at
sigma 1 and 2.  No parameter search or capacity change is performed.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

import numpy as np
import pandas as pd

PROBLEM = Path(__file__).resolve().parents[1]
REPO = PROBLEM.parents[1]
sys.path.insert(0, str(PROBLEM / "src"))

from gpu_scheduling.data import native, read_data
from gpu_scheduling.q3 import Config, POLICIES, SOURCE, TARGET, describe
from gpu_scheduling.q3_v2 import R_SHAPE, completion_cost_spec, derive_shape_limit, route_shape, simulate_shape

HORIZON = 7_776_000
CONFIGS = {
    "Rshape_sigma1": Config(60, 1, 10, True, 1, HORIZON, "q3-fixed-split-v1"),
    "Rshape_sigma2": Config(60, 1, 10, True, 2, HORIZON, "q3-fixed-split-v1"),
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(native(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def timing(frame, horizon):
    if frame.empty:
        return {"jobs": 0}
    wait = frame.start - frame.submit_time
    jct = frame.finish - frame.submit_time
    relative = frame.finish - frame.submit_time - frame.original_duration
    return {
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


def paired(base, treatment, mask, horizon):
    b = base.set_index("job_name").sort_index()
    t = treatment.set_index("job_name").sort_index()
    if not b.index.equals(t.index):
        raise AssertionError("paired schedules have different original ID sets")
    selected = pd.Series(mask, index=base.job_name).reindex(b.index).to_numpy()
    x, y = b[selected], t.loc[b.index[selected]]
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


def cohort_metrics(nodes, frame, r0, m0, config, shape_limit, duration_cutoff):
    a10 = frame.original_gpu_model == SOURCE
    a100 = frame.original_gpu_model == TARGET
    short = frame.original_duration <= duration_cutoff
    single = frame.worker_num == 1
    strata_masks = {
        "A10_short_single_worker": a10 & short & single,
        "A10_short_multi_worker": a10 & short & ~single,
        "A10_long_single_worker": a10 & ~short & single,
        "A10_long_multi_worker": a10 & ~short & ~single,
    }
    out = {
        "A10": timing(frame[a10], config.horizon_seconds),
        "native_A100": timing(frame[a100], config.horizon_seconds),
        "ALL": timing(frame, config.horizon_seconds),
        "routed_A10": timing(frame[frame.route_reason == "routed"], config.horizon_seconds),
        "unrouted_A10": timing(frame[a10 & (frame.route_reason != "routed")], config.horizon_seconds),
        "physical": describe(nodes, frame, config)["physical"],
        "routing": {
            "counts": {str(k): int(v) for k, v in frame.route_reason.value_counts().items()},
            "routed_jobs": int((frame.route_reason == "routed").sum()),
            "routed_gpu_work": float((frame.loc[frame.route_reason == "routed", "original_duration"] * frame.loc[frame.route_reason == "routed", "worker_num"] * frame.loc[frame.route_reason == "routed", "gpu_request"]).sum()),
            "routed_cpu_work": float((frame.loc[frame.route_reason == "routed", "original_duration"] * frame.loc[frame.route_reason == "routed", "worker_num"] * frame.loc[frame.route_reason == "routed", "cpu_units"]).sum() / 100),
            "all_A10_gpu_work": float((frame.loc[a10, "original_duration"] * frame.loc[a10, "worker_num"] * frame.loc[a10, "gpu_request"]).sum()),
            "all_A10_cpu_work": float((frame.loc[a10, "original_duration"] * frame.loc[a10, "worker_num"] * frame.loc[a10, "cpu_units"]).sum() / 100),
        },
        "shape": {
            "candidate": R_SHAPE,
            "derived_cpu_per_gpu_limit": shape_limit,
            "criterion": "cpu_request / gpu_request <= derived donor CPU/GPU capacity ratio",
            "comparison": "V1 R0 at same policy and sigma",
        },
        "strata": {name: timing(frame[mask], config.horizon_seconds) for name, mask in strata_masks.items()},
        "strata_definition": {"duration_cutoff_seconds": duration_cutoff, "short": "original_duration <= cutoff", "long": "original_duration > cutoff", "single_worker": "worker_num == 1", "multi_worker": "worker_num > 1"},
    }
    routed = frame[frame.route_reason == "routed"]
    out["routed_distribution"] = {
        "jobs": int(len(routed)),
        "original_duration_seconds": {"min": int(routed.original_duration.min()), "median": float(routed.original_duration.quantile(.5)), "p95": float(routed.original_duration.quantile(.95)), "max": int(routed.original_duration.max())} if len(routed) else None,
        "effective_duration_seconds": {"min": int(routed.duration.min()), "median": float(routed.duration.quantile(.5)), "p95": float(routed.duration.quantile(.95)), "max": int(routed.duration.max())} if len(routed) else None,
        "worker_num_counts": {str(k): int(v) for k, v in routed.worker_num.value_counts().sort_index().items()},
        "gpu_request_counts": {str(k): int(v) for k, v in routed.gpu_request.value_counts().sort_index().items()},
    }
    out["routing"]["routed_gpu_work_fraction"] = out["routing"]["routed_gpu_work"] / out["routing"]["all_A10_gpu_work"]
    out["routing"]["routed_cpu_work_fraction"] = out["routing"]["routed_cpu_work"] / out["routing"]["all_A10_cpu_work"]
    out["q3_describe"] = describe(nodes, frame, config)
    out["paired_R0"] = {
        "A10": paired(r0, frame, r0.original_gpu_model.to_numpy() == SOURCE, config.horizon_seconds),
        "native_A100": paired(r0, frame, r0.original_gpu_model.to_numpy() == TARGET, config.horizon_seconds),
        "ALL": paired(r0, frame, np.ones(len(r0), dtype=bool), config.horizon_seconds),
    }
    out["paired_M0"] = {
        "A10": paired(m0, frame, m0.original_gpu_model.to_numpy() == SOURCE, config.horizon_seconds),
        "native_A100": paired(m0, frame, m0.original_gpu_model.to_numpy() == TARGET, config.horizon_seconds),
        "ALL": paired(m0, frame, np.ones(len(m0), dtype=bool), config.horizon_seconds),
    }
    r0_short = r0.original_duration <= duration_cutoff
    r0_single = r0.worker_num == 1
    m0_short = m0.original_duration <= duration_cutoff
    m0_single = m0.worker_num == 1
    r0_masks = {
        "A10_short_single_worker": (r0.original_gpu_model == SOURCE) & r0_short & r0_single,
        "A10_short_multi_worker": (r0.original_gpu_model == SOURCE) & r0_short & ~r0_single,
        "A10_long_single_worker": (r0.original_gpu_model == SOURCE) & ~r0_short & r0_single,
        "A10_long_multi_worker": (r0.original_gpu_model == SOURCE) & ~r0_short & ~r0_single,
    }
    m0_masks = {
        "A10_short_single_worker": (m0.original_gpu_model == SOURCE) & m0_short & m0_single,
        "A10_short_multi_worker": (m0.original_gpu_model == SOURCE) & m0_short & ~m0_single,
        "A10_long_single_worker": (m0.original_gpu_model == SOURCE) & ~m0_short & m0_single,
        "A10_long_multi_worker": (m0.original_gpu_model == SOURCE) & ~m0_short & ~m0_single,
    }
    out["paired_R0_strata"] = {name: paired(r0, frame, mask.to_numpy(), config.horizon_seconds) for name, mask in r0_masks.items()}
    out["paired_M0_strata"] = {name: paired(m0, frame, mask.to_numpy(), config.horizon_seconds) for name, mask in m0_masks.items()}
    return out


def assert_native_invariance(r0, r0_ledger, treatment, treatment_ledger):
    native_ids = set(r0.loc[r0.original_gpu_model == TARGET, "job_name"])
    a = r0.set_index("job_name").loc[sorted(native_ids), ["start", "finish"]]
    b = treatment.set_index("job_name").loc[sorted(native_ids), ["start", "finish"]]
    pd.testing.assert_frame_equal(a, b, check_dtype=False)
    def native_placements(frame, ledger):
        ids = set(frame.loc[frame.original_gpu_model == TARGET, "job_name"])
        return ledger[ledger.job_name.isin(ids)].sort_values(["job_name", "node_name", "workers"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(native_placements(r0, r0_ledger), native_placements(treatment, treatment_ledger), check_dtype=False)


def load_reference(root, sigma, policy):
    if sigma == 1:
        label = "M1"
        base = root / f"{policy}_M0_jobs.csv.gz"
        r0 = root / f"{policy}_M1_jobs.csv.gz"
        bl = root / f"{policy}_M0_placements.csv.gz"
        rl = root / f"{policy}_M1_placements.csv.gz"
    else:
        base = root / "unused"
        r0 = REPO / "outputs/q3-v2-r0-sigma2" / f"S5_{policy}" / "jobs.csv.gz"
        rl = REPO / "outputs/q3-v2-r0-sigma2" / f"S5_{policy}" / "placements.csv.gz"
    if sigma == 1:
        return pd.read_csv(base), pd.read_csv(r0), pd.read_csv(rl), None, label
    m0 = pd.read_csv(root / f"{policy}_M0_jobs.csv.gz")
    return m0, pd.read_csv(r0), pd.read_csv(rl), None, "S5"


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
    limit = derive_shape_limit(nodes, 60)
    a10_durations = jobs.loc[jobs.gpu_model == SOURCE, "duration"]
    duration_cutoff = int(a10_durations.quantile(0.5))
    args.out.mkdir(parents=True)
    args.output_root.mkdir(parents=True)
    write_json(args.out / "frozen_config.json", {"candidate": R_SHAPE, "shape_limit_cpu_per_gpu": limit, "configs": {k: asdict(v) for k, v in CONFIGS.items()}})
    write_json(args.out / "candidate_B_spec.json", completion_cost_spec())
    write_json(args.out / "shape_audit.json", {"donor_nodes": 60, "donor_node_count": 60, "derived_cpu_per_gpu_limit": limit, "donor_cpu_values": sorted(nodes[nodes.gpu_model == TARGET].sort_values("node_name").head(60).cpu_num.unique().tolist()), "donor_gpu_values": sorted(nodes[nodes.gpu_model == TARGET].sort_values("node_name").head(60).gpu_capacity_num.unique().tolist()), "criterion": "cpu_request / gpu_request <= donor capacity CPU/GPU ratio"})
    status = {}
    metrics_all = {}
    references = {}
    for scenario, config in CONFIGS.items():
        status[scenario] = {}
        metrics_all[scenario] = {}
        sigma = config.sigma
        for policy in POLICIES:
            tick = time.perf_counter()
            m0, r0, r0_ledger, _unused, r0_label = load_reference(args.s0, sigma, policy)
            # V1 M1 is the R0 reference at sigma=1.  Sigma=2 R0 is the
            # previously verified S5 schedule, copied as an immutable local
            # reference from the V1 sensitivity artifact.
            frame, ledger = simulate_shape(nodes, jobs, policy, config)
            assert_native_invariance(r0, r0_ledger, frame, ledger)
            label = f"{scenario}_{policy}"
            scenario_dir = args.output_root / label
            scenario_dir.mkdir(parents=True)
            frame.to_csv(scenario_dir / "jobs.csv.gz", index=False, compression="gzip")
            ledger.to_csv(scenario_dir / "placements.csv.gz", index=False, compression="gzip")
            report = cohort_metrics(nodes, frame, r0, m0, config, limit, duration_cutoff)
            report.update({"scenario": scenario, "policy": policy, "configuration": asdict(config), "reference_scenario": r0_label, "wall_seconds": time.perf_counter() - tick, "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024})
            write_json(args.out / f"{label}_metrics.json", report)
            metrics_all[scenario][policy] = report
            status[scenario][policy] = {"status": "PASS", "output": str(scenario_dir), "wall_seconds": report["wall_seconds"], "native_invariance": "PASS"}
            print(f"{label}: simulated and native invariance PASS ({report['wall_seconds']:.2f}s)", flush=True)
    write_json(args.out / "scenario_status.json", status)
    write_json(args.out / "shape_metrics.json", metrics_all)
    manifest = {
        "schema_version": 1, "kind": "q3_v2_r_shape", "status": "PASS", "candidate": R_SHAPE,
        "base_tag": "2026-mcm-b-baseline-v1", "base_commit": "4ee2c6bfa98cf7177ff976abe73b122889437f46",
        "current_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "current_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip()),
        "data_sha256": data_hashes, "jobs": len(jobs), "nodes": len(nodes), "horizon_seconds": HORIZON,
        "shape_limit_cpu_per_gpu": limit, "duration_cutoff_seconds": duration_cutoff, "policies": list(POLICIES), "sigma_values": [1, 2],
        "r0_reference": {
            "sigma1": {"path": str(args.s0), "run_json_sha256": digest(args.s0 / "run.json")},
            "sigma2": {"path": "outputs/q3-v2-r0-sigma2/S5_*", "source_schedule_sha256": {
                policy: {
                    "jobs": digest(REPO / "outputs/q3-v2-r0-sigma2" / f"S5_{policy}/jobs.csv.gz"),
                    "placements": digest(REPO / "outputs/q3-v2-r0-sigma2" / f"S5_{policy}/placements.csv.gz"),
                } for policy in POLICIES
            }, "provenance": "copied byte-for-byte from verified V1 sensitivity output"},
        },
        "v1_source_preserved": True, "new_scheduling_runs": 4,
        "cost": {"wall_seconds": time.perf_counter() - started, "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "serial": True},
        "output_root": str(args.output_root), "command": sys.argv,
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "platform": platform.platform()},
        "candidate_B": "IMPLEMENTATION_DEFERRED: no safe arrival callback in current q3.route entry point",
    }
    write_json(args.out / "manifest.json", manifest)


if __name__ == "__main__":
    main()
