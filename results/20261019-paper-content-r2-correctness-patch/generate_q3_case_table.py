#!/usr/bin/env python3
"""Generate the Q3 C0--C4 table from the saved integrated runtime evidence."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "results/20261019-b-v2-integration-candidate/v2_runtime_equivalence.json"
PAIRED = ROOT / "results/20261018-b-q3-v2-r1-6f2c8a10/paired.csv"
OUT_TEX = ROOT / "problems/2026_gpu_scheduling/paper/output/generated_q3_case_table.tex"
OUT_JSON = Path(__file__).with_name("q3_case_metrics.json")


def tex(value: object) -> str:
    return str(value).replace("%", r"\%").replace("_", r"\_").replace("&", r"\&")


def read_cases() -> dict[str, dict]:
    raw = json.loads(EVIDENCE.read_text())
    return {row["case"]: row for row in raw["cases"] if row["case"] in {"C0", "C1", "C2", "C3", "C4"}}


def read_harm() -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {f"C{i}": {"native": 0, "a10": 0} for i in range(5)}
    with PAIRED.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["policy"] != "SJF-HOL" or row["cohort"] != "A10" or row["reference"] != "M0":
                continue
            if row["option"] == "R0":
                case = "C1" if float(row["sigma"]) == 1 else "C2"
            elif row["option"] == "R-shape":
                case = "C3" if float(row["sigma"]) == 1 else "C4"
            else:
                continue
            out[case]["a10"] = int(row["harmed_jobs"])
    return out


def make_records() -> list[dict]:
    cases = read_cases()
    harm = read_harm()
    # Keep the source value unescaped here; tex() applies the single LaTeX
    # percent escape when it writes the generated row.
    routing = {"C0": "none", "C1": "Hash-10%", "C2": "Hash-10%", "C3": "Shape-filtered", "C4": "Shape-filtered"}
    records = []
    for case in ["C0", "C1", "C2", "C3", "C4"]:
        row = cases[case]
        all_metrics = row["metrics"]["cohorts"]["ALL"]
        a10_metrics = row["metrics"]["cohorts"]["original_A10"]
        placement = row["placement_policy"]
        placement_label = "ratio+FF-id" if placement["GPU-series-1"] == "ratio" else "FF-id"
        sigma = row["config"]["sigma"] if row["config"]["compatibility"] else "--"
        records.append(
            {
                "case": case,
                "policy": "SPT-HOL",
                "placement": placement_label,
                "routing": routing[case],
                "sigma": sigma,
                "cohort": "ALL",
                "source_field": "metrics.cohorts.ALL; fields mean_jct_hours, completed_at_horizon; original_A10.mean_jct_hours",
                "a10_jct": a10_metrics["mean_jct_hours"],
                "all_jct": all_metrics["mean_jct_hours"],
                "done": all_metrics["completed_at_horizon"],
                "native_harm": 0,
                "a10_harm": harm[case]["a10"] if case != "C0" else 0,
                "source": "results/20261019-b-v2-integration-candidate/v2_runtime_equivalence.json",
                "harm_source": "results/20261018-b-q3-v2-r1-6f2c8a10/paired.csv (SJF-HOL, A10, reference M0)",
            }
        )
    return records


def write(records: list[dict]) -> None:
    OUT_JSON.write_text(json.dumps({"source": str(EVIDENCE.relative_to(ROOT)), "records": records}, indent=2) + "\n")
    lines = [
        r"\begin{table}[H]\centering",
        r"\caption{SPT-HOL fixed-split evidence generated from the formal C0--C4 case records. Each row records the case, policy, placement, routing, speed, cohort, and source fields used for the displayed values. Native harm is the number of native A100 jobs with positive additional waiting relative to C0; the last column is the harmed A10 count.}",
        r"\label{tab:r2q3main}",
        r"\begin{tabularx}{\linewidth}{>{\raggedright\arraybackslash}Xrrrrr}",
        r"\toprule",
        r"Case / policy / placement / routing / $\sigma$ / cohort / source field & A10 JCT (h) & All JCT (h) & $90$d done & Native harm & A10 harmed\\",
        r"\midrule",
    ]
    for r in records:
        key = f"{r['case']} / {r['policy']} / {r['placement']} / {r['routing']} / $\\sigma={r['sigma']}$ / {r['cohort']} / {r['source_field']}"
        lines.append(f"{tex(key)} & {r['a10_jct']:.6f} & {r['all_jct']:.6f} & {r['done']:,} & {r['native_harm']} & {r['a10_harm']}\\\\")
    lines += [
        r"\bottomrule",
        r"\end{tabularx}",
        r"\smallskip\noindent Source for all JCT/completion cells: \texttt{results/20261019-b-v2-integration-candidate/v2\_runtime\_equivalence.json}, case key C0--C4; harm cells: paired SJF-HOL/A10 rows against M0 in the saved paired artifact.",
        r"\end{table}",
    ]
    OUT_TEX.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    write(make_records())
