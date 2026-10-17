#!/usr/bin/env python3
"""Assemble the bounded K/timer and SPT-HEAD-TIME study.

This is a read-only post-processor.  It consumes the independently persisted
``run_m2b_benchmark.py`` directories and never invokes the scheduler.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from analyze_m2f_bounds import count_lower_bound, decompose, read_directory_timing, stable_id_hash
from gpu_scheduling.data import read_data


def groups(rows):
    out = {}
    for name, pred in (
        ("short_single", lambda r: r["duration"] <= 3600 and r["worker_num"] == 1),
        ("short_multi", lambda r: r["duration"] <= 3600 and r["worker_num"] > 1),
        ("long_single", lambda r: r["duration"] > 3600 and r["worker_num"] == 1),
        ("long_multi", lambda r: r["duration"] > 3600 and r["worker_num"] > 1),
    ):
        w = np.asarray([r["start"] - r["submit_time"] for r in rows if pred(r)], dtype=np.int64)
        out[name] = {"n": int(len(w)),
                     "mean_wait_hours": float(w.mean() / 3600) if len(w) else None,
                     "p99_wait_hours": float(np.quantile(w, .99) / 3600) if len(w) else None,
                     "max_wait_hours": float(w.max() / 3600) if len(w) else None}
    return out


def pair(base, candidate):
    a, b = {r["job_name"]: r for r in base}, {r["job_name"]: r for r in candidate}
    if set(a) != set(b):
        raise ValueError("paired timing sets differ")
    for jid in a:
        keys = ("submit_time", "duration", "worker_num", "gpu_request", "cpu_units")
        if any(a[jid][k] != b[jid][k] for k in keys):
            raise ValueError(f"paired input mismatch at {jid}")
    d = np.asarray([b[j]["start"] - b[j]["submit_time"] - (a[j]["start"] - a[j]["submit_time"])
                    for j in sorted(a)], dtype=np.int64)
    return {"jobs": len(d), "mean_delta_hours": float(d.mean() / 3600),
            "improved_jobs": int((d < 0).sum()), "worsened_jobs": int((d > 0).sum()),
            "unchanged_jobs": int((d == 0).sum()),
            "positive_added_wait_job_seconds": int(d[d > 0].sum()),
            "max_added_wait_hours": float(d.max() / 3600),
            "base_zero_wait_new_delay_jobs": int(((np.asarray([a[j]["start"] - a[j]["submit_time"] for j in sorted(a)]) == 0) & (d > 0)).sum())}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--runs", nargs="+", required=True,
                    help="label=benchmark.json path (benchmark child timing is resolved from it)")
    args = ap.parse_args()
    root = args.repo_root.resolve()
    if args.out.exists():
        raise SystemExit(f"output exists: {args.out}")
    args.out.mkdir(parents=True)
    raw = read_data(root / "problems/2026_gpu_scheduling/data/raw")[1]
    source = {}
    all_rows = {}
    all_records = {}
    for spec in args.runs:
        label, path = spec.split("=", 1)
        bench_path = (root / path).resolve()
        bench = json.loads(bench_path.read_text())
        rec = bench["records"][0]
        child = (bench_path.parent / rec["child_output"]).resolve()
        policy = rec["policy"]
        rows, member = read_directory_timing(child, policy)
        source[label] = {"benchmark": str(bench_path.relative_to(root)),
                         "child_output": str(child.relative_to(root)),
                         "timing": member, "timing_sha256": sha(child / f"{policy}_job_times.csv.gz"),
                         "row_count": len(rows), "job_id_sha256": stable_id_hash(r["job_name"] for r in rows),
                         "policy": policy, "configuration": bench["configuration"]}
        all_rows[label] = rows
        all_records[label] = rec

    by_size = {}
    for label, rows in all_rows.items():
        n = len(rows)
        prefix = raw[raw.gpu_model == "A10"].head(n)
        expected = {int(r.job_name): r for r in prefix.itertuples()}
        actual = {r["job_name"]: r for r in rows}
        if set(expected) != set(actual):
            raise ValueError(f"{label}: ID set does not equal formal A10 prefix")
        for jid, r in actual.items():
            x = expected[jid]
            for key, want in (("submit_time", int(x.submit_time)), ("duration", int(x.duration)),
                              ("worker_num", int(x.worker_num)), ("gpu_request", int(x.gpu_request)),
                              ("cpu_units", int(x.cpu_units))):
                if r[key] != want:
                    raise ValueError(f"{label}: input mismatch {jid}/{key}")
        capacity = int((read_data(root / "problems/2026_gpu_scheduling/data/raw")[0]
                        .query("gpu_model == 'A10'").gpu_capacity_num.sum()))
        raw_rows = [{"submit_time": int(x.submit_time), "duration": int(x.duration),
                     "worker_num": int(x.worker_num), "gpu_request": int(x.gpu_request)} for x in prefix.itertuples()]
        lower = count_lower_bound(raw_rows, capacity)
        mean = float(np.mean([r["start"] - r["submit_time"] for r in rows]) / 3600)
        dec = decompose(rows, lower["integral_q_job_seconds"], mean)
        all_records[label]["lower_bound"] = lower
        all_records[label]["decomposition"] = dec
        all_records[label]["groups"] = groups(rows)
        size = str(n)
        by_size.setdefault(size, {"capacity_gpu": capacity, "lower_bound": lower, "policies": {}})
        by_size[size]["policies"][label] = {"policy": all_records[label]["policy"],
            "metrics": all_records[label]["metrics"], "cost": all_records[label]["cost"],
            "groups": all_records[label]["groups"], "decomposition": dec,
            "validation": all_records[label].get("validation", "PASS"),
            "schedule_sha256": all_records[label]["schedule_sha256"],
            "runtime_seconds": all_records[label].get("runtime_seconds"),
            "scheduler_seconds": all_records[label].get("scheduler_seconds"),
            "validation_seconds": all_records[label].get("validation_seconds"),
            "io_seconds": all_records[label].get("io_seconds"),
            "peak_rss_kib_process": all_records[label].get("peak_rss_kib_process")}

    pairs = {}
    for size, entries in by_size.items():
        labels = list(entries["policies"])
        base = next((x for x in labels if entries["policies"][x]["policy"] == "SPT-FILL"), None)
        if base:
            for other in labels:
                if other != base:
                    pairs[f"{base}->{other}"] = pair(all_rows[base], all_rows[other])

    out = {"schema_version": 1, "kind": "q2_v2_k_timer_ablation",
           "status": "PASS", "configuration": {"theta_seconds": 604800,
           "event_modes": ["shared-timer", "arrival-completion-only"], "reservation_k": [200, 2000],
           "horizon_seconds": 7776000, "placement": "FF-id", "guardrails": {"timeout_seconds": 900, "max_rss_kib": 4194304}},
           "source": source, "results_by_job_count": by_size, "pairs": pairs,
           "execution": {"analysis_seconds": 0},
           "limitations": ["168h is exploratory, not optimized", "SPT-HEAD-TIME is a bounded candidate",
                           "results are A10-only; no 224112-job cluster claim"]}
    (args.out / "comparison.json").write_text(json.dumps(out, indent=2) + "\n")
    (args.out / "manifest.json").write_text(json.dumps({**out, "raw_sha256": {
        "node_info_df.csv": sha(root / "problems/2026_gpu_scheduling/data/raw/node_info_df.csv"),
        "job_info_clean.csv": sha(root / "problems/2026_gpu_scheduling/data/raw/job_info_clean.csv")}}, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "out": str(args.out), "sizes": list(by_size)}, indent=2))


if __name__ == "__main__":
    main()
