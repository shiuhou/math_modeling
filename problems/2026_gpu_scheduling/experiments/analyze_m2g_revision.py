#!/usr/bin/env python3
"""Read-only M2-G cross-review reconciliation.

This tool consumes persisted Q2 G2/G3 timing archives and the persisted Q3 M0
FCFS/SJF-HOL timing ledger.  It never invokes the scheduler.  The output keeps
the Q3 source provenance explicit and separates ordinary job-count waiting from
GPU-work-weighted waiting.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path
from decimal import Decimal

from gpu_scheduling.data import read_data


TIMING_FIELDS = ("job_name", "submit_time", "duration", "worker_num",
                 "gpu_request", "start", "finish")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def id_hash(ids: set[int]) -> str:
    return hashlib.sha256(("\n".join(map(str, sorted(ids))) + "\n").encode()).hexdigest()


def canonical_hash(rows: dict[int, dict]) -> str:
    payload = "".join(
        ",".join(str(row[k]) for k in TIMING_FIELDS) + "\n"
        for _, row in sorted(rows.items())
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def parse_bytes(blob: bytes, source: str) -> dict[int, dict]:
    with gzip.GzipFile(fileobj=io.BytesIO(blob), mode="rb") as gz:
        text = io.TextIOWrapper(gz).read()
    reader = csv.DictReader(io.StringIO(text, newline=""))
    required = set(TIMING_FIELDS) | {"gpu_model", "cpu_request"}
    if not required <= set(reader.fieldnames or ()):
        raise ValueError(f"{source}: incomplete timing schema")
    out: dict[int, dict] = {}
    for raw in reader:
        jid = int(raw["job_name"])
        if jid in out:
            raise ValueError(f"{source}: duplicate job {jid}")
        row = {
            "job_name": jid,
            "gpu_model": raw["gpu_model"],
            "submit_time": int(raw["submit_time"]),
            "duration": int(raw["duration"]),
            "worker_num": int(raw["worker_num"]),
            "gpu_request": int(raw["gpu_request"]),
            "cpu_request": raw["cpu_request"],
            "cpu_units": int(Decimal(raw["cpu_request"]) * 100),
            "start": int(raw["start"]),
            "finish": int(raw["finish"]),
        }
        if row["start"] < row["submit_time"] or row["finish"] != row["start"] + row["duration"]:
            raise ValueError(f"{source}: invalid timing for {jid}")
        row["wait"] = row["start"] - row["submit_time"]
        out[jid] = row
    return out


def read_gzip(path: Path) -> tuple[dict[int, dict], dict]:
    blob = path.read_bytes()
    rows = parse_bytes(blob, str(path))
    return rows, {"path": str(path), "sha256": sha256(path),
                  "row_count": len(rows), "job_id_sha256": id_hash(set(rows)),
                  "timing_canonical_sha256": canonical_hash(rows)}


def read_archive(archive: Path, member_suffix: str) -> tuple[dict[int, dict], dict]:
    with tarfile.open(archive, "r:gz") as tar:
        names = [m.name for m in tar.getmembers() if m.name.endswith(member_suffix)]
        if len(names) != 1:
            raise ValueError(f"{archive}: expected one {member_suffix}, got {names}")
        blob = tar.extractfile(names[0]).read()
    rows = parse_bytes(blob, names[0])
    return rows, {"archive": str(archive), "member": names[0],
                  "compressed_sha256": hashlib.sha256(blob).hexdigest(),
                  "row_count": len(rows), "job_id_sha256": id_hash(set(rows)),
                  "timing_canonical_sha256": canonical_hash(rows)}


def source_match(raw, rows: dict[int, dict], *, model: str = "A10") -> dict:
    expected = raw[raw.gpu_model == model]
    exp = {int(x.job_name): x for x in expected.itertuples()}
    if set(exp) != set(rows):
        raise ValueError("timing IDs do not equal the formal source set")
    for jid, row in rows.items():
        item = exp[jid]
        checks = ((row["gpu_model"], item.gpu_model, "gpu_model"),
                  (row["submit_time"], int(item.submit_time), "submit_time"),
                  (row["duration"], int(item.duration), "duration"),
                  (row["worker_num"], int(item.worker_num), "worker_num"),
                  (row["gpu_request"], int(item.gpu_request), "gpu_request"),
                  (row["cpu_units"], int(item.cpu_units), "cpu_request"))
        for got, want, name in checks:
            if got != want:
                raise ValueError(f"job {jid}: {name} mismatch")
    return {"status": "PASS", "row_count": len(rows),
            "job_id_sha256": id_hash(set(rows)), "input_match": True}


def source_match_a10_subset(raw, rows: dict[int, dict]) -> dict:
    return source_match(raw, {jid: row for jid, row in rows.items()
                              if row["gpu_model"] == "A10"})


def weighted_metrics(rows: dict[int, dict]) -> dict:
    weights = {jid: row["worker_num"] * row["gpu_request"] * row["duration"]
               for jid, row in rows.items()}
    total_wait = sum(row["wait"] for row in rows.values())
    total_work = sum(weights.values())
    weighted_wait = sum(weights[jid] * row["wait"] for jid, row in rows.items())
    return {
        "jobs": len(rows),
        "mean_wait_hours": total_wait / len(rows) / 3600,
        "gpu_work_weighted_mean_wait_hours": weighted_wait / total_work / 3600,
        "total_wait_job_seconds": total_wait,
        "total_gpu_work_seconds": total_work,
        "weighted_wait_gpu_seconds_squared": weighted_wait,
    }


def full_cluster_summary(metrics: dict) -> dict:
    pools = ("A10", "A100-SXM4-80GB", "A800-SXM4-80GB", "GPU-series-1",
             "GPU-series-2", "H800")
    out = {}
    for policy in ("FCFS", "SJF-HOL"):
        m0 = metrics[policy]["M0"]
        rows = {}
        for pool in pools:
            physical = m0["physical"][pool]
            c = m0["cohorts"].get("original_A10" if pool == "A10" else "native_A100")
            # Q3 M0 stores the non-A10 pool timing summaries under each
            # physical pool's independent evaluator, not in cohorts.
            c = physical["shared_evaluator"]
            rows[pool] = {
                "jobs": c["jobs"],
                "mean_wait_hours": c["mean_wait_hours"],
                "p95_wait_hours": c["p95_wait_hours"],
                "p99_wait_hours": c["p99_wait_hours"],
                "max_wait_hours": c["max_wait_hours"],
                "mean_jct_hours": c["mean_jct_hours"],
                "completed_at_horizon": c["completed_at_horizon"],
                "gpu_allocation_rate_at_horizon": physical["gpu_allocation_rate_at_horizon"],
                "cpu_allocation_rate_at_horizon": physical["cpu_allocation_rate_at_horizon"],
            }
        c = m0["cohorts"]["ALL"]
        rows["ALL"] = {k: c[k] for k in ("jobs", "mean_wait_hours", "p95_wait_hours",
                                           "p99_wait_hours", "max_wait_hours",
                                           "mean_jct_hours", "completed_at_horizon")}
        out[policy] = rows
    return out


def run(args) -> dict:
    root = Path(args.repo_root).resolve()
    raw = read_data(root / "problems/2026_gpu_scheduling/data/raw")[1]
    raw_a10 = raw[raw.gpu_model == "A10"]
    q3_metrics = json.loads(Path(args.q3_metrics).read_text())
    q3_manifest = json.loads(Path(args.q3_manifest).read_text())
    q1_bound = json.loads(Path(args.q1_bound).read_text())
    fcfs_all, fcfs_source = read_gzip(Path(args.fcfs_timing))
    sjf_all, sjf_source = read_gzip(Path(args.sjf_timing))
    g2, g2_source = read_archive(Path(args.g2_archive), "SPT-HOL_job_times.csv.gz")
    g3, g3_source = read_archive(Path(args.g3_archive), "SPT-FILL_job_times.csv.gz")
    fcfs = {jid: row for jid, row in fcfs_all.items() if row["gpu_model"] == "A10"}
    sjf = {jid: row for jid, row in sjf_all.items() if row["gpu_model"] == "A10"}
    checks = {
        "raw_a10_set": {"status": "PASS", "row_count": len(raw_a10),
                        "job_id_sha256": id_hash(set(int(x) for x in raw_a10.job_name))},
        "fcfs_full_timing_source": {"status": "PASS", "row_count": len(fcfs_all),
                                     "job_id_sha256": id_hash(set(fcfs_all)),
                                     "source_commit": q3_manifest["code"]["commit"]},
        "sjf_hol_full_timing_source": {"status": "PASS", "row_count": len(sjf_all),
                                        "job_id_sha256": id_hash(set(sjf_all)),
                                        "source_commit": q3_manifest["code"]["commit"]},
        "fcfs_a10_input_match": source_match(raw, fcfs),
        "sjf_hol_a10_input_match": source_match(raw, sjf),
        "q2_g2_input_match": source_match(raw, g2),
        "q2_g3_input_match": source_match(raw, g3),
    }
    if set(g2) != set(sjf) or any(
        tuple(g2[j][k] for k in TIMING_FIELDS) != tuple(sjf[j][k] for k in TIMING_FIELDS)
        for j in g2
    ):
        raise ValueError("Q2 G2 and Q3 M0 SJF-HOL A10 timing differ")
    checks["q2_g2_vs_q3_m0_sjf_hol_a10"] = {
        "status": "PASS", "row_count": len(g2),
        "id_hash_equal": id_hash(set(g2)) == id_hash(set(sjf)),
        "timing_rows_equal": True,
        "q2_g2_timing_canonical_sha256": canonical_hash(g2),
        "q3_m0_sjf_hol_a10_timing_canonical_sha256": canonical_hash(sjf),
    }
    weighted = {
        "FCFS": weighted_metrics(fcfs),
        "SPT-HOL": weighted_metrics(g2),
        "SPT-FILL": weighted_metrics(g3),
    }
    q1_a10 = q1_bound["pools"]["A10"]
    g3_cost = json.loads(Path(args.g3_benchmark).read_text())["records"][0]["cost"]
    source = {
        "q3_commit": q3_manifest["code"]["commit"],
        "q3_manifest_sha256": sha256(Path(args.q3_manifest)),
        "q3_metrics_sha256": sha256(Path(args.q3_metrics)),
        "q1_bound_source": str(Path(args.q1_bound)),
        "q1_bound_sha256": sha256(Path(args.q1_bound)),
        "q1_bound_calculation_version": q1_bound["calculation_version"],
        "q1_a10_lower_bound_hours": q1_a10["lower_bound_hours"]["approximate"],
        "timing_sources": {"FCFS": fcfs_source, "Q3-M0-SJF-HOL": sjf_source,
                           "Q2-G2-SPT-HOL": g2_source, "Q2-G3-SPT-FILL": g3_source},
    }
    return {
        "schema_version": 1,
        "kind": "q2_m2g_cross_review_revision",
        "status": "PASS",
        "external_review": {"status": "RECORDED_NOT_INDEPENDENTLY_VALIDATED",
                             "description": "Claude cross-review supplied the FILL budget interpretation and the 307844 count; this tool validates persisted denominators and timing, not the external prose."},
        "configuration": {"theta_seconds": 604800, "event_mode": "shared-timer",
                          "reservation_k": 200, "placement": "FF-id",
                          "horizon_seconds": 7776000},
        "data": {"node_info_df_sha256": sha256(root / "problems/2026_gpu_scheduling/data/raw/node_info_df.csv"),
                 "job_info_clean_sha256": sha256(root / "problems/2026_gpu_scheduling/data/raw/job_info_clean.csv"),
                 "a10_jobs": len(raw_a10), "a10_job_id_sha256": checks["raw_a10_set"]["job_id_sha256"]},
        "fill_budget_diagnostic": {
            "policy": "SPT-FILL", "budget_exhausted": 307844,
            "budget_exhausted_source": "external Claude cross-review; not a persisted G3 summary field",
            "order_builds": g3_cost["order_builds"],
            "order_builds_source": "results/20261016-b-q2-m2g-01/g3-111284-benchmark.json",
            "ratio_budget_exhausted_per_order_build": 307844 / g3_cost["order_builds"],
            "interpretation": "candidate-attempt/order-build diagnostic only; not a fraction of waiting time",
            "unverified_items": ["G3 archive does not persist budget_exhausted event count independently"],
        },
        "weighted_waiting": weighted,
        "lower_bounds": {"job_count_mean_wait_hours": 22.317930570033027,
                         "job_count_integral_job_seconds": 8941062908,
                         "gpu_work_weighted_a10_mean_wait_hours": q1_a10["lower_bound_hours"]["approximate"],
                         "gpu_work_bound_source": "Q1 fixed-pool fluid bound; CPU/node/gang relaxed"},
        "full_cluster_q3_m0_summary": full_cluster_summary(q3_metrics),
        "source_objects": source,
        "checks": checks,
        "missing_or_limited": [
            "Q3 M0 full-cluster timing is an external worktree artifact; only its hashes and derived summary are committed here",
            "Q2 has no full 224112-job run; the full-cluster table is explicitly Q3 M0 FCFS/SJF-HOL evidence",
            "GPU-work weighted lower bound is Q1's fluid bound, not the Q2 job-count bound",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", default=".")
    p.add_argument("--fcfs-timing", required=True)
    p.add_argument("--sjf-timing", required=True)
    p.add_argument("--g2-archive", required=True)
    p.add_argument("--g3-archive", required=True)
    p.add_argument("--g3-benchmark", required=True)
    p.add_argument("--q3-manifest", required=True)
    p.add_argument("--q3-metrics", required=True)
    p.add_argument("--q1-bound", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.out.exists():
        raise SystemExit(f"output exists: {args.out}")
    result = run(args)
    args.out.mkdir(parents=True)
    (args.out / "revision.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
