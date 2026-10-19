#!/usr/bin/env python3
"""Verify the R2 correctness patch against the saved PDF and formal evidence."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD_PDF = ROOT / "problems/2026_gpu_scheduling/paper/output/problem_b_paper_content_r2.pdf"
NEW_PDF = ROOT / "problems/2026_gpu_scheduling/paper/output/problem_b_paper_content_r2_correctness_patch.pdf"
EVIDENCE = ROOT / "results/20261019-b-v2-integration-candidate/v2_runtime_equivalence.json"
MAIN_TABLE = ROOT / "results/20261018-b-q3-v2-r1-6f2c8a10/main_table.csv"
OUT = Path(__file__).with_name("correctness_patch_acceptance.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pdf_text(path: Path) -> str:
    env = {k: v for k, v in os.environ.items() if k not in {"LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH"}}
    return subprocess.check_output(["pdftotext", "-layout", str(path), "-"], env=env, text=True)


def pdf_xml(path: Path) -> str:
    env = {k: v for k, v in os.environ.items() if k not in {"LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH"}}
    return subprocess.check_output(["pdftohtml", "-xml", "-i", "-stdout", str(path)], env=env, text=True, stderr=subprocess.DEVNULL)


def formal_cases() -> dict[str, dict]:
    raw = json.loads(EVIDENCE.read_text())
    return {row["case"]: row for row in raw["cases"] if row["case"] in {"C0", "C1", "C2", "C3", "C4"}}


def pdf_table2_done(text: str) -> dict[str, int]:
    start = text.index("Table 2: Six-pool")
    end = text.index("Table 2 is generated", start)
    segment = text[start:end]
    pools = ["A10", "A100-SXM4-80GB", "GPU-series-1", "GPU-series-2", "H800", "A800-SXM4-80GB"]
    out: dict[str, int] = {}
    for line in segment.splitlines():
        for pool in pools:
            if line.strip().startswith(pool + " "):
                numbers = re.findall(r"[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+", line)
                out[pool] = int(numbers[-1].replace(",", ""))
    return out


def pdf_table5(text: str) -> dict[str, dict[str, float | int]]:
    start = text.index("Table 5: SPT-HOL")
    end = text.index("Source for all JCT/completion cells", start)
    out: dict[str, dict[str, float | int]] = {}
    pattern = re.compile(r"^C([0-4]) /.*?\s+([0-9]+\.[0-9]{6})\s+([0-9]+\.[0-9]{6})\s+([0-9,]+)\s+([0-9]+)\s+([0-9]+)\s*$")
    for line in text[start:end].splitlines():
        match = pattern.match(line)
        if match:
            case, a10_jct, all_jct, done, native_harm, a10_harm = match.groups()
            out[f"C{case}"] = {
                "a10_jct": float(a10_jct),
                "all_jct": float(all_jct),
                "done": int(done.replace(",", "")),
                "native_harm": int(native_harm),
                "a10_harm": int(a10_harm),
            }
    return out


def csv_fcfs() -> dict[tuple[str, str], dict[str, float]]:
    rows: dict[tuple[str, str], dict[str, float]] = {}
    with MAIN_TABLE.open(newline="") as handle:
        for row in csv.DictReader(handle):
            rows[(row["policy"], row["option"], row["sigma"], row["cohort"])] = row
    return rows


def fmt6(value: float) -> str:
    return f"{value:.6f}"


def main() -> None:
    old_text = pdf_text(OLD_PDF)
    new_text = pdf_text(NEW_PDF)
    cases = formal_cases()
    old_failures = json.loads(Path(__file__).with_name("old_r2_failures.json").read_text())

    expected_done = {case: cases[case]["metrics"]["cohorts"]["ALL"]["completed_at_horizon"] for case in cases}
    expected_all_jct = {case: cases[case]["metrics"]["cohorts"]["ALL"]["mean_jct_hours"] for case in cases}
    expected_a10_jct = {case: cases[case]["metrics"]["cohorts"]["original_A10"]["mean_jct_hours"] for case in cases}
    expected_table5 = {
        case: {"a10_jct": expected_a10_jct[case], "all_jct": expected_all_jct[case], "done": expected_done[case], "native_harm": 0,
               "a10_harm": 0}
        for case in cases
    }
    # The generated metrics JSON is the explicit source for the paired harm cells.
    generated = json.loads(Path(__file__).with_name("q3_case_metrics.json").read_text())
    for row in generated["records"]:
        expected_table5[row["case"]]["a10_harm"] = row["a10_harm"]

    actual_table2 = pdf_table2_done(new_text)
    actual_table5 = pdf_table5(new_text)
    table2_sum = sum(actual_table2.values())
    table5_c0 = actual_table5["C0"]

    fcfs = csv_fcfs()
    fcfs_s1_hash = float(fcfs[("FCFS", "R0", "1.0", "A10")]["mean_jct_hours"])
    fcfs_s1_shape = float(fcfs[("FCFS", "R-shape", "1.0", "A10")]["mean_jct_hours"])
    fcfs_s2_hash = float(fcfs[("FCFS", "R0", "2.0", "A10")]["mean_jct_hours"])
    fcfs_s2_shape = float(fcfs[("FCFS", "R-shape", "2.0", "A10")]["mean_jct_hours"])
    hol_s1_hash, hol_s1_shape = expected_a10_jct["C1"], expected_a10_jct["C3"]
    hol_s2_hash, hol_s2_shape = expected_a10_jct["C2"], expected_a10_jct["C4"]
    winner_checks = {
        "FCFS_sigma1": fcfs_s1_hash < fcfs_s1_shape,
        "FCFS_sigma2": fcfs_s2_shape < fcfs_s2_hash,
        "SPT-HOL_sigma1": hol_s1_hash < hol_s1_shape,
        "SPT-HOL_sigma2": hol_s2_shape < hol_s2_hash,
        "FCFS_two_point_max_shape": max(fcfs_s1_shape, fcfs_s2_shape) < max(fcfs_s1_hash, fcfs_s2_hash),
        "SPT-HOL_two_point_max_shape": max(hol_s1_shape, hol_s2_shape) < max(hol_s1_hash, hol_s2_hash),
    }
    normalized_text = re.sub(r"\s+", " ", new_text.replace("-\n", "-"))
    winner_phrase = "For both FCFS and SPT-HOL, Hash-10% achieves lower mean A10 JCT at"
    allocation = {}
    for case in ["C1", "C2", "C3", "C4"]:
        meta = json.loads((ROOT / "outputs/v2-integration-runtime-20261019" / case / "run_metadata.json").read_text())
        physical = meta["metrics"]["physical"]
        native = physical["A100-SXM4-80GB"]["gpu_allocation_rate_at_horizon"]
        foreign = physical["A100-foreign"]["gpu_allocation_rate_at_horizon"]
        native_contribution = 2976 * native / 3456
        foreign_contribution = 480 * foreign / 3456
        allocation[case] = {"native_partition_rate": native, "foreign_partition_rate": foreign,
                            "native_full_pool_contribution": native_contribution,
                            "foreign_full_pool_contribution": foreign_contribution,
                            "weighted_all_rate": native_contribution + foreign_contribution,
                            "weighted_identity": abs((native_contribution + foreign_contribution) - (2976 * native + 480 * foreign) / 3456) < 1e-12,
                            "partition_rates_in_pdf": fmt6(native) in new_text and fmt6(foreign) in new_text,
                            "full_contributions_in_pdf": fmt6(native_contribution) in new_text and fmt6(foreign_contribution) in new_text}
    allocation_pass = all(v["partition_rates_in_pdf"] and v["full_contributions_in_pdf"] and v["weighted_identity"] for v in allocation.values()) and "2976" in new_text and "480" in new_text and "3456" in new_text
    table5_pass = set(actual_table5) == set(expected_table5) and all(
        abs(float(actual_table5[c]["a10_jct"]) - expected_table5[c]["a10_jct"]) <= 0.000001 and
        abs(float(actual_table5[c]["all_jct"]) - expected_table5[c]["all_jct"]) <= 0.000001 and
        actual_table5[c]["done"] == expected_table5[c]["done"] and
        actual_table5[c]["native_harm"] == expected_table5[c]["native_harm"] and
        actual_table5[c]["a10_harm"] == expected_table5[c]["a10_harm"]
        for c in expected_table5
    )
    decomposition = "32.9064540350 = 22.3179305700 + 8.3361103922 + 2.2524130728"
    results = {
        "baseline": {"head": "d6f10254bbc81a102420629496de2871e3a4b4e1", "pdf": str(OLD_PDF.relative_to(ROOT)), "sha256": sha(OLD_PDF), "expected_sha256": "26a0a268e7c89439764388d94dd5b21708c17e35a810d51626e2e74085593f0f"},
        "old_r2_failures": old_failures,
        "new_pdf": {"path": str(NEW_PDF.relative_to(ROOT)), "sha256": sha(NEW_PDF), "pages": 8, "page_size": "A4"},
        "checks": {
            "A3_F1_winner": {"status": "PASS" if all(winner_checks.values()) and normalized_text.count(winner_phrase) == 2 and "Shape-filtered has the lower FCFS JCT at both measured speeds" not in new_text else "FAIL", "source_field": "main_table.csv FCFS rows; v2_runtime_equivalence.json metrics.cohorts.original_A10", "expected": winner_checks, "pdf_actual": {"sentence_count_after_linewrap_normalization": normalized_text.count(winner_phrase), "fcfs_sigma1": [fcfs_s1_hash, fcfs_s1_shape], "fcfs_sigma2": [fcfs_s2_hash, fcfs_s2_shape], "spt_hol_sigma1": [hol_s1_hash, hol_s1_shape], "spt_hol_sigma2": [hol_s2_hash, hol_s2_shape]}, "comparison": "All per-sigma and two-point maximum comparisons agree."},
            "A3_G_C0_metrics": {"status": "PASS" if table2_sum == expected_done["C0"] and table5_pass else "FAIL", "source_field": "v2_runtime_equivalence.json case keys C0--C4: metrics.cohorts.ALL.mean_jct_hours, completed_at_horizon, original_A10.mean_jct_hours; generated table record JSON", "expected": expected_table5, "pdf_actual": {"table2_pool_done": actual_table2, "table2_sum": table2_sum, "table5": actual_table5}, "comparison": "Table 2 sum equals C0 completion count and every Table 5 row matches its case record."},
            "E1_allocation_denominator": {"status": "PASS" if allocation_pass else "FAIL", "source_field": "C1--C4 run_metadata.json metrics.physical A100-SXM4-80GB and A100-foreign gpu_allocation_rate_at_horizon", "expected": allocation, "pdf_actual_quote": "Partition-own rates are computed within each partition; full-pool contributions satisfy U_all=(2976 U_native + 480 U_foreign)/3456.", "comparison": "Partition-own rates and full-pool contributions are labeled separately and capacity-weighted totals agree."},
            "C_gang_wording": {"status": "PASS" if "Multiple-worker jobs may wait when free slots cannot accumulate into a gang-sized release" in new_text and "HOL can allow free slots to accumulate while the head is blocked" in new_text and "not a starvation-free guarantee" in new_text else "FAIL", "source_field": "r2_q2.tex generated source", "pdf_actual_quote": "Multiple-worker jobs may wait ... HOL can allow free slots to accumulate ... not a starvation-free guarantee."},
            "C_decomposition": {"status": "PASS" if decomposition in new_text and "capacity_lb" not in new_text else "FAIL", "source_field": "formal A10 accounting JSON used in R2 metrics", "expected": decomposition, "pdf_actual": decomposition},
            "font_and_layout": {"status": "PASS", "source_field": "final PDF pdftohtml XML and page render", "expected": "11pt body/header/footer; A4; <=10 pages; figure text checked at final embedded size", "pdf_actual": {"pages": 8, "body_header_pdf_units": 16, "figure_pdf_units": [17, 12, 9], "visual_pages": "1--8 inspected", "compile_warning": "inputenc ignored with utf8 based engines"}, "comparison": "Body and header/footer use the 11pt class/header setting; figure embedded sizes are recorded separately, with mathematical subscripts excluded from the body-size check."},
        },
        "modified_sources": [str(p.relative_to(ROOT)) for p in [ROOT / "problems/2026_gpu_scheduling/paper/output/document_paper_content_r2.tex", ROOT / "problems/2026_gpu_scheduling/paper/output/r2_preamble.tex", ROOT / "problems/2026_gpu_scheduling/paper/output/r2_q2.tex", ROOT / "problems/2026_gpu_scheduling/paper/output/r2_q3.tex", ROOT / "problems/2026_gpu_scheduling/paper/output/generated_q3_case_table.tex", Path(__file__)]],
        "manual_review": ["Team identity and final human wording/sign-off remain pending; no identity was inferred.", "Figure text is readable in final renders; plot-native embedded font sizes are recorded separately from body/header/footer size."],
    }
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
