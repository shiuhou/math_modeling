#!/usr/bin/env python3
"""Assemble the bounded M2-G comparisons from persisted job timings.

This is a read-only analysis tool.  It does not invoke the simulator and does
not replace the shared evaluator.  Archived M2-E timings and the three M2-G
runs are checked against the formal raw loader before paired summaries are
written.
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

import numpy as np

from gpu_scheduling.data import read_data


POLICIES = ("SPT-FILL", "SPT-HOL", "SPT-URGENT-HOL", "SPT-URGENT-TIME",
            "SPT-URGENT-FIXED", "SPT-URGENT-FLEX")
OLD_POLICIES = ("SPT-FILL", "SPT-URGENT-HOL", "SPT-URGENT-TIME",
                "SPT-URGENT-FIXED", "SPT-URGENT-FLEX")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def id_hash(ids: set[int]) -> str:
    return hashlib.sha256(("\n".join(map(str, sorted(ids))) + "\n").encode()).hexdigest()


def parse_csv(blob: bytes, source: str) -> dict[int, dict]:
    with gzip.GzipFile(fileobj=io.BytesIO(blob)) as f:
        text = f.read().decode("utf-8")
    rows = csv.DictReader(io.StringIO(text, newline=""))
    out = {}
    required = {"job_name", "gpu_model", "submit_time", "duration", "worker_num",
                "gpu_request", "cpu_request", "start", "finish"}
    if not required <= set(rows.fieldnames or ()):
        raise ValueError(f"{source}: incomplete timing schema")
    for row in rows:
        jid = int(row["job_name"])
        if jid in out:
            raise ValueError(f"{source}: duplicate job {jid}")
        start, finish = int(row["start"]), int(row["finish"])
        submit, duration = int(row["submit_time"]), int(row["duration"])
        if start < submit or finish != start + duration:
            raise ValueError(f"{source}: invalid timing for {jid}")
        out[jid] = {
            "job_name": jid, "gpu_model": row["gpu_model"],
            "submit_time": submit, "duration": duration,
            "worker_num": int(row["worker_num"]), "gpu_request": int(row["gpu_request"]),
            "start": start, "finish": finish,
            "wait": start - submit, "jct": finish - submit,
        }
    return out


def direct_timing(directory: Path, policy: str) -> tuple[dict[int, dict], dict]:
    path = directory / f"{policy}_job_times.csv.gz"
    blob = path.read_bytes()
    return parse_csv(blob, str(path)), {"path": str(path), "sha256": sha256(path)}


def archived_timing(archive: Path, policy: str) -> tuple[dict[int, dict], dict, dict]:
    suffix = f"/{policy}_job_times.csv.gz"
    with tarfile.open(archive, "r:gz") as tar:
        timing = [m for m in tar.getmembers() if m.name.endswith(suffix)]
        summaries = [m for m in tar.getmembers()
                     if m.name.endswith("/summary.json") and policy.lower() in m.name.lower()]
        if len(timing) != 1 or len(summaries) != 1:
            raise ValueError(f"archive members for {policy} are ambiguous")
        compressed = tar.extractfile(timing[0]).read()
        summary = json.loads(tar.extractfile(summaries[0]).read())
    return parse_csv(compressed, timing[0].name), {
        "archive": str(archive), "member": timing[0].name,
        "compressed_sha256": hashlib.sha256(compressed).hexdigest(),
    }, summary


def validate_raw(rows: dict[int, dict], raw) -> dict:
    expected = raw[raw.gpu_model == "A10"].head(len(rows))
    exp = {int(r.job_name): r for r in expected.itertuples()}
    if set(exp) != set(rows):
        raise ValueError("timing job IDs do not equal the formal A10 prefix")
    for jid, row in rows.items():
        r = exp[jid]
        checks = ((row["gpu_model"], r.gpu_model, "gpu_model"),
                  (row["submit_time"], int(r.submit_time), "submit_time"),
                  (row["duration"], int(r.duration), "duration"),
                  (row["worker_num"], int(r.worker_num), "worker_num"),
                  (row["gpu_request"], int(r.gpu_request), "gpu_request"))
        for got, want, name in checks:
            if got != want:
                raise ValueError(f"job {jid} input mismatch in {name}")
    return {"jobs": len(rows), "job_id_sha256": id_hash(set(rows)), "input_match": True}


def metrics(rows: dict[int, dict], summary: dict) -> dict:
    waits = np.asarray([r["wait"] for r in rows.values()], dtype=np.int64)
    out = {"jobs": len(rows), "mean_wait_hours": float(waits.mean() / 3600),
           "p95_wait_hours": float(np.quantile(waits, .95) / 3600),
           "p99_wait_hours": float(np.quantile(waits, .99) / 3600),
           "max_wait_hours": float(waits.max() / 3600),
           "mean_jct_hours": float(np.mean([r["jct"] for r in rows.values()]) / 3600)}
    record = summary.get("results", [{}])[0]
    sm = record.get("metrics", summary.get("metrics", summary))
    for key in ("completed_at_horizon", "final_completion_days",
                "gpu_allocation_rate_at_horizon", "cpu_allocation_rate_at_horizon"):
        if key in sm:
            out[key] = sm[key]
    out["runtime_seconds"] = record.get("runtime_seconds", summary.get("runtime_seconds_total"))
    out["scheduler_seconds"] = record.get("scheduler_seconds")
    out["validation_seconds"] = record.get("validation_seconds")
    out["io_seconds"] = record.get("io_seconds")
    out["peak_rss_kib"] = record.get("peak_rss_kib_process", summary.get("peak_rss_kib_process"))
    return out


def groups(rows: dict[int, dict]) -> dict:
    specs = (("short_single", lambda r: r["duration"] <= 3600 and r["worker_num"] == 1),
             ("short_multi", lambda r: r["duration"] <= 3600 and r["worker_num"] > 1),
             ("long_single", lambda r: r["duration"] > 3600 and r["worker_num"] == 1),
             ("long_multi", lambda r: r["duration"] > 3600 and r["worker_num"] > 1))
    out = {}
    for name, pred in specs:
        waits = np.asarray([r["wait"] for r in rows.values() if pred(r)], dtype=np.int64)
        out[name] = {"n": int(len(waits)),
                     "mean_wait_hours": float(waits.mean() / 3600) if len(waits) else None,
                     "p99_wait_hours": float(np.quantile(waits, .99) / 3600) if len(waits) else None,
                     "max_wait_hours": float(waits.max() / 3600) if len(waits) else None}
    return out


def pair(base: dict[int, dict], candidate: dict[int, dict]) -> dict:
    if set(base) != set(candidate):
        raise ValueError("paired timing sets differ")
    if any((base[j]["submit_time"], base[j]["duration"], base[j]["worker_num"], base[j]["gpu_request"]) !=
           (candidate[j]["submit_time"], candidate[j]["duration"], candidate[j]["worker_num"], candidate[j]["gpu_request"])
           for j in base):
        raise ValueError("paired timing inputs differ")
    delta = np.asarray([candidate[j]["wait"] - base[j]["wait"] for j in sorted(base)], dtype=np.int64)
    bw = np.asarray([base[j]["wait"] for j in sorted(base)], dtype=np.int64)
    return {"jobs": len(delta), "mean_delta_hours": float(delta.mean() / 3600),
            "improved_jobs": int((delta < 0).sum()), "worsened_jobs": int((delta > 0).sum()),
            "unchanged_jobs": int((delta == 0).sum()),
            "positive_added_wait_job_seconds": int(delta[delta > 0].sum()),
            "max_added_wait_hours": float(delta.max() / 3600),
            "base_zero_wait_new_delay_jobs": int(((bw == 0) & (delta > 0)).sum())}


def relativize(value, root: Path):
    """Keep persisted evidence portable when inputs were passed as absolutes."""
    if isinstance(value, dict):
        return {k: relativize(v, root) for k, v in value.items()}
    if isinstance(value, list):
        return [relativize(v, root) for v in value]
    if isinstance(value, str):
        try:
            return str(Path(value).resolve().relative_to(root))
        except (ValueError, OSError):
            return value
    return value


def run(args):
    root = Path(args.repo_root).resolve()
    if args.out.exists():
        raise ValueError(f"output exists: {args.out}")
    raw = read_data(root / "problems/2026_gpu_scheduling/data/raw")[1]
    archive = Path(args.archive).resolve()
    old = {}
    sources = {}
    summaries = {}
    for policy in OLD_POLICIES:
        old[policy], sources[policy], summaries[policy] = archived_timing(archive, policy)
    direct = {
        "SPT-HOL": Path(args.g1_timing).resolve(),
        "FULL-SPT-HOL": Path(args.g2_timing).resolve(),
        "FULL-SPT-FILL": Path(args.g3_timing).resolve(),
    }
    current = {}
    current_summaries = {}
    for key, directory in direct.items():
        policy = "SPT-HOL" if key != "FULL-SPT-FILL" else "SPT-FILL"
        if key == "FULL-SPT-HOL": policy = "SPT-HOL"
        current[key], sources[key] = direct_timing(directory, policy)
        current_summaries[key] = json.loads((directory / "summary.json").read_text())
    # The G1 direct timing is the ordinary SPT-HOL entry in the 65k table.
    old["SPT-HOL"] = current["SPT-HOL"]
    summaries["SPT-HOL"] = current_summaries["SPT-HOL"]
    sources["SPT-HOL"] = sources["SPT-HOL"]
    validation = {key: validate_raw(rows, raw) for key, rows in old.items()}
    full_validation = {key: validate_raw(rows, raw) for key, rows in current.items() if key != "SPT-HOL"}
    # Full runs are supplied as the complete A10 set; validate_raw uses its size.
    full_validation["FULL-SPT-HOL"] = validate_raw(current["FULL-SPT-HOL"], raw)
    full_validation["FULL-SPT-FILL"] = validate_raw(current["FULL-SPT-FILL"], raw)
    decomp_root = root / "results/20261015-b-q2-m2f-01/gap_decomposition.json"
    old_decomp = json.loads(decomp_root.read_text())["policies"]
    g1_decomp = json.loads((root / "results/20261016-b-q2-m2g-g1-01/gap_decomposition.json").read_text())["policies"]["SPT-HOL"]
    full_decomp = {
        "FULL-SPT-HOL": json.loads((root / "results/20261016-b-q2-m2g-g2-01/gap_decomposition.json").read_text())["policies"]["SPT-HOL"],
        "FULL-SPT-FILL": json.loads((root / "results/20261016-b-q2-m2g-g3-01/gap_decomposition.json").read_text())["policies"]["SPT-FILL"],
    }
    def row(policy, rows, summary, decomp):
        m = metrics(rows, summary)
        d = {k: decomp[k] for k in ("capacity_lower_bound_hours", "within_window_gap_hours", "beyond_duration_wait_hours", "mean_to_capacity_lb", "w_greater_than_p_fraction")}
        return {"policy": policy, "metrics": m, "groups": groups(rows), "decomposition": d,
                "source": {"code_commit": summary.get("code_commit"), "source_sha256": summary.get("source_sha256")},
                "timing_source": sources.get(policy)}
    prefix_rows = []
    for p in ("SPT-FILL", "SPT-HOL", "SPT-URGENT-HOL", "SPT-URGENT-TIME", "SPT-URGENT-FIXED", "SPT-URGENT-FLEX"):
        d = g1_decomp if p == "SPT-HOL" else old_decomp[p]
        prefix_rows.append(row(p, old[p], summaries[p], d))
    full_rows = [row("SPT-HOL", current["FULL-SPT-HOL"], current_summaries["FULL-SPT-HOL"], full_decomp["FULL-SPT-HOL"]),
                 row("SPT-FILL", current["FULL-SPT-FILL"], current_summaries["FULL-SPT-FILL"], full_decomp["FULL-SPT-FILL"])]
    output = {
        "schema_version": 1, "kind": "q2_m2g_bounded_comparison", "status": "PASS",
        "configuration": {"model": "A10", "theta_seconds": 604800, "event_mode": "shared-timer",
                          "reservation_k": 200, "horizon_seconds": 7776000, "placement": "first-fit ascending node_name"},
        "data": {"node_info_df_sha256": sha256(root / "problems/2026_gpu_scheduling/data/raw/node_info_df.csv"),
                 "job_info_clean_sha256": sha256(root / "problems/2026_gpu_scheduling/data/raw/job_info_clean.csv"),
                 "a10_total_jobs": int((raw.gpu_model == "A10").sum()), "capacity_gpu": 2494},
        "prefix_65536": {"status": "PASS", "strategies": prefix_rows,
                         "pair_spt_fill_to_spt_hol": pair(old["SPT-FILL"], old["SPT-HOL"]),
                         "validation": validation},
        "full_a10_111284": {"status": "PASS", "strategies": full_rows,
                             "pair_spt_fill_to_spt_hol": pair(current["FULL-SPT-FILL"], current["FULL-SPT-HOL"]),
                             "validation": full_validation},
        "limitations": ["theta=168h is exploratory, not calibrated optimum",
                        "M2-E urgent timings are retained from their committed source; core source hashes are compared",
                        "this is A10 only, not the full 224112-job cluster"]}
    args.out.mkdir(parents=True)
    output = relativize(output, root)
    (args.out / "comparison.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", default=".")
    p.add_argument("--archive", required=True)
    p.add_argument("--g1-timing", required=True)
    p.add_argument("--g2-timing", required=True)
    p.add_argument("--g3-timing", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(run(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
