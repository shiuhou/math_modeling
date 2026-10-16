#!/usr/bin/env python3
"""Independently replay one persisted M2-A pressure run."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

PROBLEM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROBLEM / "src"))
sys.path.insert(0, str(PROBLEM / "experiments"))
import pandas as pd
from gpu_scheduling.data import read_data
from gpu_scheduling.validation import validate, validate_reservations
from verify_intake import compare_inputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PROBLEM / "data/raw")
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output exists; choose a new file")
    record = json.loads((args.run / "summary.json").read_text())
    nodes, raw_jobs, hashes = read_data(args.data)
    if hashes != record["data_sha256"]:
        raise ValueError("pressure input hash mismatch")
    jobs = raw_jobs[raw_jobs.gpu_model == record["model"]].head(int(record["jobs"])).copy()
    pool = nodes[nodes.gpu_model == record["model"]].reset_index(drop=True)
    checks = []
    for item in record["results"]:
        policy = item["policy"]
        for suffix in ("job_times.csv.gz", "node_placements.csv.gz", "reservations.json"):
            path = args.run / f"{policy}_{suffix}"
            if not path.is_file():
                raise ValueError(f"missing pressure output {path.name}")
            if record["outputs"].get(path.name) != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError(f"pressure output hash mismatch {path.name}")
        frame = pd.read_csv(args.run / f"{policy}_job_times.csv.gz")
        compare_inputs(jobs, frame)
        schedule_jobs = jobs.set_index("job_name").loc[frame.job_name].reset_index()
        schedule_jobs["start"] = frame.start.to_numpy()
        schedule_jobs["finish"] = frame.finish.to_numpy()
        placement = pd.read_csv(args.run / f"{policy}_node_placements.csv.gz")
        if set(placement.job_name) != set(frame.job_name):
            raise ValueError("pressure placement IDs incomplete")
        lookup = {int(j): i for i, j in enumerate(frame.job_name)}
        node_lookup = {int(n): i for i, n in enumerate(pool.node_name)}
        plans = [[] for _ in range(len(frame))]
        for jid, nid, workers in placement.itertuples(index=False, name=None):
            plans[lookup[int(jid)]].append((node_lookup[int(nid)], int(workers)))
        validate(pool, schedule_jobs, schedule_jobs.start.to_numpy(), schedule_jobs.finish.to_numpy(), plans)
        payload = json.loads((args.run / f"{policy}_reservations.json").read_text())
        validate_reservations(pool, schedule_jobs, {
            "starts": schedule_jobs.start.to_numpy(), "ends": schedule_jobs.finish.to_numpy(),
            "plans": plans, "reservations": payload["reservations"],
            "events": payload["events"], "policy": policy,
            "reservation_evidence_schema_version": payload.get("reservation_evidence_schema_version", 1),
        })
        checks.append({"policy": policy, "jobs": len(frame), "ledger_rows": len(placement),
                       "capacity_replay": "PASS", "reservation_replay": "PASS"})
    result = {"status": "PASS", "scope": "A10 bounded pressure", "checks": checks,
              "source_summary": "summary.json"}
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print("PASS: independent pressure ledger and reservation replay")


if __name__ == "__main__":
    main()
