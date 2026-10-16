#!/usr/bin/env python3
"""Check supplied evidence against current input and shared metrics, without resimulation.

The archived per-job CSVs have no node placement ledger: capacity validation
cannot be inferred from these checks or from an embedded historical PASS string.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import io
import json
import math
from pathlib import Path
import sys
from zipfile import ZipFile

PROBLEM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROBLEM / "src"))

import pandas as pd
from gpu_scheduling.data import read_data
from gpu_scheduling.evaluation import metrics

INPUT_COLUMNS = ["gpu_model", "submit_time", "duration", "worker_num", "gpu_request", "cpu_request"]


def read_member(archive, suffix):
    matches = [entry for entry in archive.infolist() if entry.filename.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"Expected one archive member ending in {suffix}")
    return archive.read(matches[0])


def compare_inputs(current, saved):
    if current.job_name.duplicated().any() or saved.job_name.duplicated().any():
        raise ValueError("Duplicate job IDs")
    if set(current.job_name) != set(saved.job_name):
        raise ValueError("Saved and current job ID sets differ")
    current = current.set_index("job_name").sort_index()
    saved = saved.set_index("job_name").sort_index()
    differences = {}
    for column in INPUT_COLUMNS:
        a, b = current[column], saved[column]
        if column == "gpu_model":
            count = int((a != b).sum())
        else:
            count = sum(Decimal(str(x)) != Decimal(str(y)) for x, y in zip(a, b))
        differences[column] = count
    if any(differences.values()):
        raise ValueError(f"Input values differ: {differences}")
    return differences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-zip", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=PROBLEM / "data/raw")
    parser.add_argument("--out", type=Path, required=True, help="New JSON file")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output exists; choose a new file")
    nodes, jobs, hashes = read_data(args.data_dir)
    checks = {}
    with ZipFile(args.research_zip) as archive:
        accounting = json.loads(read_member(archive, "calculations/data_audit.json"))
        reference = json.loads(read_member(archive, "calculations/baseline_metrics.json"))
        horizon = accounting["times"]["last_submit_seconds"]
        for policy in ("FCFS", "SJF-HOL"):
            blob = read_member(archive, f"calculations/{policy}_job_times.csv.gz")
            frame = pd.read_csv(io.BytesIO(blob), compression="gzip")
            differences = compare_inputs(jobs, frame)
            verified = []
            for row in (r for r in reference if r["policy"] == policy):
                model = row["gpu_model"]
                subset = frame if model == "ALL" else frame[frame.gpu_model == model]
                pool = nodes if model == "ALL" else nodes[nodes.gpu_model == model]
                measured = metrics({"jobs": subset, "starts": subset.start.to_numpy(),
                                    "ends": subset.finish.to_numpy()}, pool, horizon)
                mismatches = {key: {"saved": row[key], "recomputed": value}
                              for key, value in measured.items()
                              if not math.isclose(float(value), float(row[key]), rel_tol=1e-11, abs_tol=1e-10)}
                if mismatches:
                    raise ValueError(f"{policy}/{model}: metric disagreement {mismatches}")
                verified.append(model)
            checks[policy] = {
                "jobs": len(frame), "input_field_differences": differences,
                "input_comparison": "PASS", "metric_recalculation": "PASS",
                "gpu_models_checked": verified, "horizon_seconds": horizon,
                "saved_job_times_sha256": hashlib.sha256(blob).hexdigest(),
                "capacity_replay": "BLOCKED: archived timing CSV lacks node placements",
                "fresh_simulation": "NOT_RUN",
            }
    result = {
        "kind": "intake_evidence_check", "research_zip_sha256": hashlib.sha256(args.research_zip.read_bytes()).hexdigest(),
        "current_data_sha256": hashes, "historical_data_sha256": accounting["hashes"],
        "node_bytes_match": hashes["node_info_df.csv"] == accounting["hashes"]["node_info_df.csv"],
        "job_bytes_match": hashes["job_info_clean.csv"] == accounting["hashes"]["job_info_clean.csv"],
        "historical_original_job_bytes_available": False,
        "checks": checks,
        "limitations": "Numeric input fields and stored metric arithmetic checked only; "
                       "this does not establish historical node feasibility, rerun algorithms, "
                       "or verify the source-code ZIP paper claims.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("PASS: both saved schedules match current input fields; all saved pool/global metrics recomputed")


if __name__ == "__main__":
    main()
