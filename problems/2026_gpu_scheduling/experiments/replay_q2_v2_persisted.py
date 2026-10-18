#!/usr/bin/env python3
"""Read-only replay of one persisted Q2-V2 artifact set.

This never invokes a scheduler.  It loads the saved timing, placement,
reservation and event ledgers and applies the independent validators.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import tempfile
import pandas as pd
from gpu_scheduling.data import read_data
from gpu_scheduling.validation import validate_persisted, validate_reservations

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
Q2_WORKTREE = Path("/home/shiuhou/mm/math_modeling-b-q2-k-ablation")

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--evidence-index", type=Path, default=ROOT.parent.parent / "results/20261018-b-q2-v2-r1-01/evidence_index.json")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    evidence = json.loads(args.evidence_index.read_text())[args.case]
    raw_nodes, raw_jobs, raw_hashes = read_data(RAW)
    expected_hashes = evidence["data_sha256"]
    if raw_hashes != expected_hashes:
        raise AssertionError(f"raw hash mismatch: {raw_hashes} != {expected_hashes}")
    bench_name = Path(evidence["benchmark"]["path"]).stem.replace("q2-v2-", "")
    # benchmark stem is e.g. q2-v2-65k-a1; output folder uses the same suffix.
    output_root = Q2_WORKTREE / "outputs" / ("q2-v2-" + bench_name)
    candidates = list(output_root.glob("a10-*/SPT-*_job_times.csv.gz"))
    if len(candidates) != 1:
        raise AssertionError(f"expected one timing ledger in {output_root}, found {len(candidates)}")
    times_path = candidates[0]
    stem = times_path.name[:-len("_job_times.csv.gz")]
    placement_path = times_path.with_name(stem + "_node_placements.csv.gz")
    reservation_path = times_path.with_name(stem + "_reservations.json")
    if not placement_path.exists() or not reservation_path.exists():
        raise FileNotFoundError(f"incomplete persisted artifact set for {args.case}")
    cfg = json.loads((output_root / "benchmark.json").read_text())["configuration"]
    n = int(cfg["jobs"] [0] if isinstance(cfg["jobs"], list) else cfg["jobs"])
    jobs = raw_jobs[raw_jobs.gpu_model == "A10"].head(n).copy()
    nodes = raw_nodes[raw_nodes.gpu_model == "A10"].sort_values("node_name").reset_index(drop=True)
    persisted = json.loads(reservation_path.read_text())
    times = pd.read_csv(times_path)
    # R1 artifacts predate the strict validator's explicit wait/cpu_units
    # columns.  Derive only those adapter columns from the saved raw fields;
    # never alter the source artifact or fill a missing promise/event ledger.
    required = {"job_name", "gpu_model", "submit_time", "duration", "worker_num", "gpu_request", "cpu_request", "start", "finish"}
    if not required <= set(times):
        raise ValueError(f"missing timing fields: {sorted(required - set(times))}")
    times["cpu_units"] = (times["cpu_request"] * 100).round().astype("int64")
    times["wait"] = times["start"] - times["submit_time"]
    with tempfile.TemporaryDirectory(prefix="q2-persisted-adapter-") as tmp:
        adapted_times = Path(tmp) / "job_times.csv"
        times.to_csv(adapted_times, index=False)
        # Formal CSV adapter checks identity, timing arithmetic and node-level replay.
        base = validate_persisted(nodes, jobs, adapted_times, placement_path)
    times = times.sort_values("job_name", kind="stable").reset_index(drop=True)
    ledger = pd.read_csv(placement_path)
    node_index = {int(name): i for i, name in enumerate(nodes.node_name)}
    groups = {int(j): [(node_index[int(node)], int(workers)) for node, workers in g[["node_name", "workers"]].itertuples(index=False, name=None)] for j, g in ledger.groupby("job_name")}
    # Event indices are the scheduler's submit/job-name order, not job-name order.
    sim_jobs = jobs.reset_index(drop=True)
    sim_groups = {int(j): groups[int(j)] for j in sim_jobs.job_name}
    plans = [sim_groups[int(j)] for j in sim_jobs.job_name]
    timing_by = times.set_index("job_name")
    starts = sim_jobs.job_name.map(timing_by.start).to_numpy(dtype="int64")
    ends = sim_jobs.job_name.map(timing_by.finish).to_numpy(dtype="int64")
    replay_result = dict(persisted)
    replay_result.update({"starts": starts.tolist(), "ends": ends.tolist(), "plans": [[list(x) for x in p] for p in plans], "policy": persisted.get("policy", cfg["policies"][0])})
    validate_reservations(nodes, sim_jobs, replay_result)
    expected_artifacts = {a["path"].split("/", 1)[1]: a for a in evidence["artifacts"]}
    artifact_paths = {
        "reservations": reservation_path,
        "phase_log": times_path.parent / "phase_log.jsonl",
        "placements": placement_path,
        "timing": times_path,
    }
    actual_artifacts = {}
    for key, artifact in expected_artifacts.items():
        name = Path(key).name
        if "reservations" in name:
            path = artifact_paths["reservations"]
        elif name == "phase_log.jsonl":
            path = artifact_paths["phase_log"]
        elif "node_placements" in name:
            path = artifact_paths["placements"]
        elif "job_times" in name:
            path = artifact_paths["timing"]
        else:
            raise AssertionError(f"unknown evidence artifact: {key}")
        actual_artifacts[key] = sha(path)
    for key, value in actual_artifacts.items():
        expected = expected_artifacts[key]["expected_sha256"]
        if value != expected:
            raise AssertionError(f"artifact hash mismatch: {key}")
    result = {
        "case": args.case, "status": "PASS", "validator": "gpu_scheduling.validation.validate_persisted + validate_reservations",
        "validator_source_commit": "integration/b-v2-candidate working tree",
        "input_hashes": {"node_info_df.csv": raw_hashes["node_info_df.csv"], "job_info_clean.csv": raw_hashes["job_info_clean.csv"]},
        "jobs": len(jobs), "job_id_count": len(set(int(x) for x in jobs.job_name)), "nodes": len(nodes),
        "timing_path": str(times_path), "placement_path": str(placement_path), "reservation_path": str(reservation_path),
        "artifact_hashes": actual_artifacts, "csv_validation": base,
        "reservation_event_count": len(persisted.get("events", [])), "reservation_count": len(persisted.get("reservations", [])),
        "historical_scope": "read-only persisted artifact replay; no scheduler invocation",
        "source_availability": "LOCAL_ONLY",
    }
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
