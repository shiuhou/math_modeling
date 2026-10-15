#!/usr/bin/env python3
"""Compute the Q2 M2-F job-count lower bound and exact waiting decomposition.

The tool is read-only with respect to the scheduler and consumes persisted
M2-E timing evidence.  It intentionally implements its own CSV/archive reader
and lower-bound scan instead of importing a simulator or evaluator.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import resource
import subprocess
import tarfile
import time
from collections import Counter
from pathlib import Path
from typing import Iterable

import pandas as pd

from gpu_scheduling.data import read_data


POLICIES = (
    "SPT-FILL",
    "SPT-URGENT-HOL",
    "SPT-URGENT-TIME",
    "SPT-URGENT-FIXED",
    "SPT-URGENT-FLEX",
)
REQUIRED_TIMING_COLUMNS = {
    "job_name", "gpu_model", "submit_time", "duration", "worker_num",
    "gpu_request", "cpu_request", "start", "finish",
}


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def stable_id_hash(ids: Iterable[int]) -> str:
    payload = "\n".join(str(int(j)) for j in sorted(ids)).encode()
    return sha256_bytes(payload)


def scaled_cpu(value: str) -> int:
    # The formal loader uses two decimal CPU units.  Decimal-looking CSV text
    # such as 4.0 therefore compares exactly after this checked conversion.
    from decimal import Decimal, InvalidOperation

    try:
        scaled = Decimal(str(value)) * 100
    except InvalidOperation as exc:
        raise ValueError(f"invalid cpu_request {value!r}") from exc
    if scaled != scaled.to_integral_value():
        raise ValueError(f"cpu_request is not representable in 1/100 units: {value}")
    return int(scaled)


def _q_from_hist(hist: dict[int, int], active: int, capacity: int,
                 widths: tuple[int, ...]) -> int:
    """Return the minimum number of active jobs removed to fit GPU capacity."""
    remaining = capacity
    kept = 0
    for width in widths:
        if remaining <= 0:
            break
        count = hist.get(width, 0)
        if count:
            take = min(count, remaining // width)
            kept += take
            remaining -= take * width
    return active - kept


def count_lower_bound(rows: list[dict[str, int]], capacity: int) -> dict:
    """Integrate q(t) exactly over half-open event intervals.

    Events at t are applied after [previous_t, t) is integrated.  End events
    and arrivals at the same timestamp are aggregated before the next interval,
    which implements r <= t < r+p exactly.
    """
    events: dict[int, Counter[int]] = {}
    width_hist: Counter[int] = Counter()
    for row in rows:
        width = int(row["worker_num"]) * int(row["gpu_request"])
        if width <= 0:
            raise ValueError("GPU width must be positive")
        start = int(row["submit_time"])
        end = start + int(row["duration"])
        events.setdefault(start, Counter())[width] += 1
        events.setdefault(end, Counter())[width] -= 1

    widths = tuple(sorted({width for event in events.values() for width in event}))
    active = 0
    previous = None
    integral = 0
    peak_q = 0
    positive_seconds = 0
    intervals = 0
    for timestamp in sorted(events):
        if previous is not None and timestamp > previous:
            q = _q_from_hist(width_hist, active, capacity, widths)
            delta = timestamp - previous
            integral += q * delta
            peak_q = max(peak_q, q)
            if q > 0:
                positive_seconds += delta
            intervals += 1
        changes = events[timestamp]
        for width, delta in changes.items():
            width_hist[width] += delta
            active += delta
            if width_hist[width] < 0:
                raise AssertionError("negative active width count")
            if width_hist[width] == 0:
                del width_hist[width]
        previous = timestamp

    if active != 0 or width_hist:
        raise AssertionError("event scan did not drain active jobs")
    return {
        "capacity_gpu": int(capacity),
        "job_count": len(rows),
        "event_records": 2 * len(rows),
        "event_timestamps": len(events),
        "integration_intervals": intervals,
        "integral_q_job_seconds": int(integral),
        "lower_bound_mean_hours": integral / (3600 * len(rows)),
        "peak_q_jobs": int(peak_q),
        "q_positive_seconds": int(positive_seconds),
        "width_histogram": {str(k): int(v) for k, v in sorted(
            Counter(int(r["worker_num"]) * int(r["gpu_request"]) for r in rows).items())},
        "integral_end_seconds": max(
            int(r["submit_time"]) + int(r["duration"]) for r in rows
        ),
    }


def brute_q(widths: Iterable[int], capacity: int) -> int:
    """Small-case oracle for tests; never used by the formal scan."""
    widths = [int(x) for x in widths]
    kept = 0
    remaining = capacity
    for width in sorted(widths):
        if width <= remaining:
            remaining -= width
            kept += 1
    return len(widths) - kept


def _read_csv_bytes(blob: bytes, source: str) -> list[dict]:
    with gzip.GzipFile(fileobj=io.BytesIO(blob)) as stream:
        raw = stream.read()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
    if reader.fieldnames is None or not REQUIRED_TIMING_COLUMNS <= set(reader.fieldnames):
        raise ValueError(f"{source}: timing schema is missing required columns")
    rows = []
    seen = set()
    for row in reader:
        jid = int(row["job_name"])
        if jid in seen:
            raise ValueError(f"{source}: duplicate job_name {jid}")
        seen.add(jid)
        parsed = {
            "job_name": jid,
            "gpu_model": row["gpu_model"],
            "submit_time": int(row["submit_time"]),
            "duration": int(row["duration"]),
            "worker_num": int(row["worker_num"]),
            "gpu_request": int(row["gpu_request"]),
            "cpu_units": scaled_cpu(row["cpu_request"]),
            "start": int(row["start"]),
            "finish": int(row["finish"]),
        }
        if parsed["start"] < parsed["submit_time"]:
            raise ValueError(f"{source}: negative waiting time for {jid}")
        if parsed["finish"] != parsed["start"] + parsed["duration"]:
            raise ValueError(f"{source}: finish mismatch for {jid}")
        rows.append(parsed)
    return rows


def read_archive_timing(archive: Path, policy: str) -> tuple[list[dict], dict]:
    suffix = f"/{policy}_job_times.csv.gz"
    with tarfile.open(archive, "r:gz") as tar:
        members = [m for m in tar.getmembers() if m.name.endswith(suffix)]
        if len(members) != 1:
            raise ValueError(f"expected one {suffix}, found {len(members)}")
        member = members[0]
        if member.name.startswith("/") or ".." in Path(member.name).parts:
            raise ValueError(f"unsafe archive member {member.name}")
        extracted = tar.extractfile(member)
        if extracted is None:
            raise ValueError(f"cannot read {member.name}")
        compressed = extracted.read()
    rows = _read_csv_bytes(compressed, member.name)
    return rows, {
        "member": member.name,
        "compressed_sha256": sha256_bytes(compressed),
        "row_count": len(rows),
    }


def read_directory_timing(directory: Path, policy: str) -> tuple[list[dict], dict]:
    path = directory / f"{policy}_job_times.csv.gz"
    if not path.is_file():
        raise ValueError(f"missing timing file: {path}")
    compressed = path.read_bytes()
    return _read_csv_bytes(compressed, str(path)), {
        "path": str(path),
        "compressed_sha256": sha256_bytes(compressed),
        "row_count": len(_read_csv_bytes(compressed, str(path))),
    }


def raw_a10_prefix(raw_jobs: pd.DataFrame, count: int) -> pd.DataFrame:
    # This is deliberately the M2-E rule, after the formal loader's stable
    # submit_time/job_name ordering, rather than a re-sorted archive order.
    return raw_jobs[raw_jobs.gpu_model == "A10"].head(count).copy()


def validate_against_raw(rows: list[dict], raw: pd.DataFrame) -> dict:
    expected = raw_a10_prefix(raw, len(rows))
    if len(expected) != len(rows):
        raise ValueError("raw A10 prefix is shorter than persisted timing")
    expected_by_id = {int(r.job_name): r for r in expected.itertuples()}
    actual_by_id = {int(r["job_name"]): r for r in rows}
    if set(expected_by_id) != set(actual_by_id):
        raise ValueError("persisted job IDs differ from formal A10 prefix")
    for jid, actual in actual_by_id.items():
        wanted = expected_by_id[jid]
        fields = (
            (actual["gpu_model"], wanted.gpu_model, "gpu_model"),
            (actual["submit_time"], int(wanted.submit_time), "submit_time"),
            (actual["duration"], int(wanted.duration), "duration"),
            (actual["worker_num"], int(wanted.worker_num), "worker_num"),
            (actual["gpu_request"], int(wanted.gpu_request), "gpu_request"),
            (actual["cpu_units"], int(wanted.cpu_units), "cpu_units"),
        )
        for got, want, field in fields:
            if got != want:
                raise ValueError(f"job {jid} input mismatch in {field}: {got!r} != {want!r}")
    return {
        "jobs": len(rows),
        "job_id_sha256": stable_id_hash(actual_by_id),
        "input_match": True,
    }


def decompose(rows: list[dict], lower_bound_job_seconds: int,
              expected_mean_hours: float) -> dict:
    waits = [int(row["start"]) - int(row["submit_time"]) for row in rows]
    durations = [int(row["duration"]) for row in rows]
    total_wait = sum(waits)
    within_total = sum(min(wait, duration) for wait, duration in zip(waits, durations))
    beyond_total = sum(max(wait - duration, 0) for wait, duration in zip(waits, durations))
    within_gap = within_total - lower_bound_job_seconds
    if within_gap < 0:
        raise ValueError(f"negative within-window gap: {within_gap}")
    decomposition_sum = lower_bound_job_seconds + within_gap + beyond_total
    if decomposition_sum != total_wait:
        raise AssertionError("waiting decomposition does not close in integer seconds")
    mean_hours = total_wait / (3600 * len(rows))
    if not math.isclose(mean_hours, expected_mean_hours, rel_tol=0, abs_tol=1e-9):
        raise ValueError(f"mean wait mismatch: {mean_hours} != {expected_mean_hours}")

    def hours(value: int) -> float:
        return value / (3600 * len(rows))

    return {
        "jobs": len(rows),
        "total_wait_job_seconds": total_wait,
        "mean_wait_hours": mean_hours,
        "capacity_lower_bound_job_seconds": lower_bound_job_seconds,
        "capacity_lower_bound_hours": hours(lower_bound_job_seconds),
        "within_window_total_job_seconds": within_total,
        "within_window_gap_job_seconds": within_gap,
        "within_window_gap_hours": hours(within_gap),
        "beyond_duration_wait_job_seconds": beyond_total,
        "beyond_duration_wait_hours": hours(beyond_total),
        "decomposition_sum_job_seconds": decomposition_sum,
        "residual_job_seconds": decomposition_sum - total_wait,
        "mean_to_capacity_lb": mean_hours / hours(lower_bound_job_seconds),
        "fractions_of_mean": {
            "capacity_lower_bound": hours(lower_bound_job_seconds) / mean_hours,
            "within_window_gap": hours(within_gap) / mean_hours,
            "beyond_duration_wait": hours(beyond_total) / mean_hours,
        },
        "w_greater_than_p_count": sum(wait > duration for wait, duration in zip(waits, durations)),
        "w_greater_than_p_fraction": sum(wait > duration for wait, duration in zip(waits, durations)) / len(rows),
        "w_equal_p_count": sum(wait == duration for wait, duration in zip(waits, durations)),
        "w_zero_count": sum(wait == 0 for wait in waits),
        "wait_max_seconds": max(waits),
    }


def source_hashes(root: Path) -> dict[str, str]:
    paths = (
        "problems/2026_gpu_scheduling/src/gpu_scheduling/data.py",
        "problems/2026_gpu_scheduling/src/gpu_scheduling/simulator.py",
        "problems/2026_gpu_scheduling/src/gpu_scheduling/validation.py",
        "problems/2026_gpu_scheduling/src/gpu_scheduling/evaluation.py",
        "problems/2026_gpu_scheduling/experiments/analyze_m2f_bounds.py",
    )
    return {path: sha256_bytes((root / path).read_bytes()) for path in paths}


def git_state(root: Path) -> dict:
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=root, text=True
    ).splitlines()
    return {"commit": commit, "dirty": bool(status), "status_entries": status}


def run(args: argparse.Namespace) -> dict:
    started = time.perf_counter()
    root = Path(args.repo_root).resolve()
    archive = Path(args.archive).resolve() if args.archive else None
    timing_dir = Path(args.timing_dir).resolve() if args.timing_dir else None
    comparison_path = Path(args.comparison).resolve()
    m2e_manifest_path = Path(args.m2e_manifest).resolve()
    output = Path(args.out).resolve()
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    output.mkdir(parents=True)

    nodes, jobs, data_hashes = read_data(root / "problems/2026_gpu_scheduling/data/raw")
    prefix = raw_a10_prefix(jobs, args.jobs)
    if len(prefix) != args.jobs:
        raise ValueError("requested A10 prefix is unavailable")
    capacity = int(nodes.loc[nodes.gpu_model == "A10", "gpu_capacity_num"].sum())
    raw_rows = [
        {
            "job_name": int(row.job_name),
            "gpu_model": row.gpu_model,
            "submit_time": int(row.submit_time),
            "duration": int(row.duration),
            "worker_num": int(row.worker_num),
            "gpu_request": int(row.gpu_request),
            "cpu_units": int(row.cpu_units),
        }
        for row in prefix.itertuples()
    ]
    lower = count_lower_bound(raw_rows, capacity)
    comparison = json.loads(comparison_path.read_text()) if comparison_path.is_file() else {}
    if comparison and comparison.get("status") != "PASS":
        raise ValueError("M2-E comparison is not PASS")
    expected = {
        item["policy"]: item
        for item in comparison.get("strategies", [])
        if item.get("policy") in POLICIES
    }
    if not args.policies:
        raise ValueError("at least one policy is required")
    if archive is not None and set(expected) != set(POLICIES):
        raise ValueError("M2-E comparison does not contain all five policies")

    validations = {}
    decompositions = {}
    for policy in args.policies:
        if archive is not None:
            rows, member = read_archive_timing(archive, policy)
        else:
            rows, member = read_directory_timing(timing_dir, policy)
        if len(rows) != args.jobs:
            raise ValueError(f"{policy}: expected {args.jobs} rows, got {len(rows)}")
        check = validate_against_raw(rows, jobs)
        check["timing_member"] = member
        validations[policy] = check
        expected_mean = float(expected[policy]["metrics"]["mean_wait_hours"]) if policy in expected else sum(
            int(row["start"]) - int(row["submit_time"]) for row in rows
        ) / (3600 * len(rows))
        decompositions[policy] = decompose(
            rows,
            lower["integral_q_job_seconds"],
            expected_mean,
        )

    elapsed = time.perf_counter() - started
    peak_rss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "schema_version": 1,
        "kind": "q2_m2f_bounds_and_gap_decomposition",
        "status": "PASS",
        "configuration": {
            "jobs": args.jobs,
            "gpu_model": "A10",
            "capacity_gpu": capacity,
            "source_schedule_theta_seconds": 604800,
            "source_schedule_event_mode": "shared-timer",
            "source_schedule_reservation_k": 200,
            "source_schedule_placement": "first-fit ascending node_name",
            "source_schedule_horizon_seconds": 7776000,
            "lower_bound_time_unit": "integer seconds",
        },
        "data": {
            "source_sha256": data_hashes,
            "job_id_sha256": stable_id_hash(int(x) for x in prefix.job_name),
            "prefix_rule": "read_data sorted jobs; A10 filter; head(65536)",
        },
        "archive": ({
            "path": str(archive.relative_to(root)),
            "sha256": sha256_bytes(archive.read_bytes()),
        } if archive is not None else {"timing_dir": str(timing_dir.relative_to(root))}),
        "comparison": ({
            "path": str(comparison_path.relative_to(root)),
            "sha256": sha256_bytes(comparison_path.read_bytes()),
        } if comparison_path.is_file() else None),
        "m2e_manifest": ({
            "path": str(m2e_manifest_path.relative_to(root)),
            "sha256": sha256_bytes(m2e_manifest_path.read_bytes()),
        } if m2e_manifest_path.is_file() else None),
        "analysis_code": {
            "git": git_state(root),
            "source_sha256": source_hashes(root),
        },
        "lower_bound": lower,
        "input_validation": validations,
        "decomposition": decompositions,
        "execution": {
            "seconds": elapsed,
            "peak_rss_kib": peak_rss_kib,
            "python": __import__("platform").python_version(),
            "dependencies": {
                "numpy": __import__("numpy").__version__,
                "pandas": pd.__version__,
            },
        },
        "interpretation": {
            "bound_scope": "GPU-capacity relaxation; ignores CPU packing, node shape, gang placement, HOL and policy rules",
            "decomposition_scope": "exact integer accounting for these non-preemptive persisted timings",
            "causal_warning": "within-window gap is not an attributable or necessarily eliminable policy loss",
        },
    }
    (output / "lower_bound.json").write_text(json.dumps({
        "status": "PASS", "lower_bound": lower, "data": result["data"],
    }, indent=2) + "\n")
    (output / "gap_decomposition.json").write_text(json.dumps({
        "status": "PASS", "capacity_lower_bound_hours": lower["lower_bound_mean_hours"],
        "policies": decompositions,
    }, indent=2) + "\n")
    (output / "input_validation.json").write_text(json.dumps(validations, indent=2) + "\n")
    (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--archive", type=Path)
    source.add_argument("--timing-dir", type=Path)
    parser.add_argument("--comparison", type=Path,
                        default=Path("results/20261015-b-q2-m2e-01/comparison-65536.json"))
    parser.add_argument("--policies", nargs="+", default=list(POLICIES))
    parser.add_argument(
        "--m2e-manifest", type=Path,
        default=Path("results/20261015-b-q2-m2e-01/manifest.json"),
    )
    parser.add_argument("--jobs", type=int, default=65536)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps({
        "status": result["status"],
        "out": str(Path(args.out)),
        "lower_bound_hours": result["lower_bound"]["lower_bound_mean_hours"],
        "seconds": result["execution"]["seconds"],
        "peak_rss_kib": result["execution"]["peak_rss_kib"],
    }, indent=2))


if __name__ == "__main__":
    main()
