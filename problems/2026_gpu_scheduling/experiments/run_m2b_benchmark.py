#!/usr/bin/env python3
"""Run bounded M2-B cost probes with one clean child process per policy.

The child is the existing single DES pressure runner.  This wrapper only
coordinates independent invocations and records their summaries, so each
policy has its own peak RSS and cannot inherit a previous strategy's
``ru_maxrss``.  Full per-job outputs stay in the ignored output directory;
the committed evidence is the compact benchmark summary and hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

PROBLEM = Path(__file__).resolve().parents[1]


def process_rss_kib(pid: int) -> int | None:
    """Read Linux child RSS without adding a runtime dependency."""
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (FileNotFoundError, PermissionError, ValueError):
        return None
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PROBLEM / "data/raw")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="A10")
    parser.add_argument("--jobs", type=int, nargs="+", default=[16_384, 32_768])
    parser.add_argument("--theta-seconds", type=int, nargs="+", default=[4_860_000])
    parser.add_argument("--short-theta-seconds", type=int, default=4)
    parser.add_argument("--reservation-k", type=int, default=200)
    parser.add_argument("--event-mode", choices=("shared-timer", "arrival-completion-only"), default="shared-timer")
    parser.add_argument("--timeout-seconds", type=float, default=None,
                        help="per-policy child wall timeout; omitted means no parent timeout")
    parser.add_argument("--max-rss-kib", type=int, default=None,
                        help="per-policy child RSS limit sampled from /proc; omitted means no RSS limit")
    parser.add_argument("--policies", nargs="+",
                        default=["SPT-URGENT-TIME", "SPT-URGENT-FIXED", "SPT-URGENT-FLEX", "EASY-NR"])
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output exists; choose a new directory")
    if any(n <= 0 for n in args.jobs) or any(t < 0 for t in args.theta_seconds) or args.short_theta_seconds < 0:
        parser.error("jobs and thresholds must be nonnegative (jobs strictly positive)")
    if args.timeout_seconds is not None and args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    if args.max_rss_kib is not None and args.max_rss_kib <= 0:
        parser.error("--max-rss-kib must be positive")
    args.out.mkdir(parents=True)
    records = []
    def threshold_label(theta: int) -> str:
        if theta == 4_860_000:
            return "historical-anchor-1350h"
        if theta == 604_800:
            return "exploratory-168h"
        return "configured-threshold"

    probe_specs = [(int(n), int(theta), threshold_label(int(theta)))
                   for n in args.jobs for theta in args.theta_seconds]
    if args.short_theta_seconds not in args.theta_seconds:
        probe_specs.append((min(args.jobs), int(args.short_theta_seconds), "mechanism-short-threshold"))
    runner = PROBLEM / "experiments" / "run_m2a_pressure.py"
    for jobs, theta, threshold_label in probe_specs:
        for policy in args.policies:
            tag = f"{args.model.lower()}-{jobs}-theta{theta}-{policy.lower()}"
            child_out = args.out / tag
            started = time.perf_counter()
            command = [sys.executable, str(runner), "--data", str(args.data),
                       "--out", str(child_out), "--model", args.model,
                       "--jobs", str(jobs), "--theta-seconds", str(theta),
                       "--reservation-k", str(args.reservation_k), "--event-mode", args.event_mode,
                       "--policies", policy]
            child = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            observed_peak_rss = 0
            stop_reason = None
            while child.poll() is None:
                rss = process_rss_kib(child.pid)
                if rss is not None:
                    observed_peak_rss = max(observed_peak_rss, rss)
                    if args.max_rss_kib is not None and rss > args.max_rss_kib:
                        stop_reason = "RSS_LIMIT"
                        child.kill()
                        break
                if args.timeout_seconds is not None and time.perf_counter() - started > args.timeout_seconds:
                    stop_reason = "TIMEOUT"
                    child.kill()
                    break
                time.sleep(0.05)
            stdout, stderr = child.communicate()
            wall = time.perf_counter() - started
            if child.returncode != 0 or stop_reason is not None:
                status = stop_reason or "FAILED"
                phase_path = child_out / "phase_log.jsonl"
                latest_phase = None
                if phase_path.exists():
                    # Diagnostic log is sparse and bounded; ignore a partial
                    # final write if the child was killed during append.
                    for line in phase_path.read_text().splitlines():
                        try:
                            latest_phase = json.loads(line)
                        except json.JSONDecodeError:
                            pass
                failure = {"latest_phase": latest_phase,
                    "phase_log": str(phase_path.relative_to(args.out)),
                    "status": status, "tag": tag, "jobs": jobs, "theta_seconds": theta,
                    "threshold_label": threshold_label,
                    "policy": policy, "elapsed_seconds": wall,
                    "observed_peak_rss_kib": observed_peak_rss,
                    "returncode": child.returncode, "command": command,
                    "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-4000:],
                }
                (args.out / f"{tag}-status.json").write_text(json.dumps(failure, indent=2) + "\n")
                records.append(failure)
                continue
            summary_path = child_out / "summary.json"
            summary = json.loads(summary_path.read_text())
            child = summary["results"][0]
            records.append({
                "jobs": jobs, "theta_seconds": theta, "threshold_label": threshold_label,
                "policy": child["policy"], "child_output": str(child_out.relative_to(args.out)),
                "child_wall_seconds": wall, "child_summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
                "peak_rss_kib_process": child["peak_rss_kib_process"],
                "scheduler_seconds": child["scheduler_seconds"],
                "validation_seconds": child["validation_seconds"],
                "metrics_seconds": child["metrics_seconds"], "io_seconds": child["io_seconds"],
                "input_seconds": child["input_seconds"], "runtime_seconds": child["runtime_seconds"],
                "schedule_sha256": child["schedule_sha256"], "reservations": child["reservations"],
                "cost": child["cost"], "metrics": child["metrics"],
                "validation": child["validation"],
            })
    output = {
        "schema_version": 1, "kind": "m2b_bounded_cost_probe",
        "status": "PASS" if all(r.get("status", "PASS") == "PASS" for r in records) else "INCOMPLETE",
        "configuration": {"model": args.model, "jobs": args.jobs, "theta_seconds": args.theta_seconds,
                          "short_theta_seconds": args.short_theta_seconds,
                          "reservation_k": args.reservation_k, "event_mode": args.event_mode,
                          "policies": args.policies, "placement": "first-fit ascending node_name",
                          "horizon_seconds": 7_776_000,
                          "timeout_seconds": args.timeout_seconds, "max_rss_kib": args.max_rss_kib},
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "records": records,
        "note": "Each record is an independent child process; no performance claim is made for unrun full trace.",
    }
    path = args.out / "benchmark.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    if output["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
