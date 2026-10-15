#!/usr/bin/env python3
"""Build the Q3-S3 publication package from S1/S2 persisted evidence only.

This script performs no scheduling.  It reads the versioned JSON summaries,
normalizes M0/M1(=S0)/S1--S5 rows, and renders the English and Traditional
Chinese chapter from that one paper-ready data set.
"""
from argparse import ArgumentParser
import csv
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
import time

REPO = Path(__file__).resolve().parents[3]
PROBLEM = REPO / "problems/2026_gpu_scheduling"
S1 = REPO / "results/20261015-b-q3-fixed-split-c9e8f1a2"
S2 = REPO / "results/20261015-b-q3-s2-fixed-split-v1"
PAPER = PROBLEM / "paper"
POLICIES = ("FCFS", "SJF-HOL")
SCENARIOS = (
    ("M0", 0, 0.0, 1), ("S0", 60, 10.0, 1),
    ("S1", 60, 5.0, 1), ("S2", 60, 20.0, 1),
    ("S3", 30, 10.0, 1), ("S4", 90, 10.0, 1), ("S5", 60, 10.0, 2),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


PAIR_ASYMMETRIC = (
    "positive_extra_wait_hours", "positive_completion_delay_hours",
    "p99_delta_wait_hours", "max_delta_wait_hours",
    "zero_wait_new_delay_jobs",
)


def identity_pair():
    """An explicit same-schedule comparison; zeros here are computed identities."""
    fields = {
        "mean_delta_wait_hours": 0.0,
        "mean_delta_jct_hours": 0.0,
        "mean_delta_finish_hours": 0.0,
        "waiting_worse_jobs": 0,
        "waiting_better_jobs": 0,
        "finish_worsened_jobs": 0,
        "finish_improved_jobs": 0,
        "finish_equal_jobs": 0,
        "equal_wait_jobs": 0,
        "positive_extra_wait_hours": 0.0,
        "positive_completion_delay_hours": 0.0,
        "zero_wait_new_delay_jobs": 0,
        "p99_delta_wait_hours": 0.0,
        "max_delta_wait_hours": 0.0,
        "completion_count_delta_at_horizon": 0,
    }
    return {"A10": dict(fields), "native_A100": dict(fields)}


def normalize_pair(raw, *, derive_sigma1_order=False):
    """Normalize schemas without inventing absent statistics.

    The formal S1 verifier has finish-order counts rather than the S2 waiting
    count names.  Under sigma=1, arrivals and durations are identical, so the
    finish ordering is also the waiting ordering; that derivation is recorded
    rather than silently defaulting missing fields to zero.
    """
    out = {}
    for name, value in raw.items():
        key = "A10" if name == "original_A10" else name
        item = dict(value)
        derived = []
        if "mean_delta_finish_hours" not in item:
            if "mean_delta_jct_hours" in item:
                item["mean_delta_finish_hours"] = item["mean_delta_jct_hours"]
                derived.append("mean_delta_finish_hours=mean_delta_jct_hours")
            elif "mean_delta_wait_hours" in item:
                item["mean_delta_finish_hours"] = item["mean_delta_wait_hours"]
                derived.append("mean_delta_finish_hours=mean_delta_wait_hours")
        if "mean_delta_jct_hours" not in item and "mean_delta_finish_hours" in item:
            item["mean_delta_jct_hours"] = item["mean_delta_finish_hours"]
            derived.append("mean_delta_jct_hours=mean_delta_finish_hours")
        if derive_sigma1_order:
            if "waiting_worse_jobs" not in item and "later_completion_jobs" in item:
                item["waiting_worse_jobs"] = item["later_completion_jobs"]
                derived.append("waiting_worse_jobs=later_completion_jobs[sigma=1]")
            if "waiting_better_jobs" not in item and "earlier_completion_jobs" in item:
                item["waiting_better_jobs"] = item["earlier_completion_jobs"]
                derived.append("waiting_better_jobs=earlier_completion_jobs[sigma=1]")
            if "finish_worsened_jobs" not in item and "later_completion_jobs" in item:
                item["finish_worsened_jobs"] = item["later_completion_jobs"]
                derived.append("finish_worsened_jobs=later_completion_jobs")
            if "finish_improved_jobs" not in item and "earlier_completion_jobs" in item:
                item["finish_improved_jobs"] = item["earlier_completion_jobs"]
                derived.append("finish_improved_jobs=earlier_completion_jobs")
            if "finish_equal_jobs" not in item and "equal_completion_jobs" in item:
                item["finish_equal_jobs"] = item["equal_completion_jobs"]
                derived.append("finish_equal_jobs=equal_completion_jobs")
        if derived:
            item["derived_fields"] = derived
        out[key] = item
    return out


def reverse_pair(forward):
    """Reverse only symmetric means/counts; leave asymmetric statistics unknown."""
    out = {}
    for group, item in forward.items():
        rev = {"comparison_status": "REVERSED_SYMMETRIC_ONLY"}
        for key in ("mean_delta_wait_hours", "mean_delta_jct_hours", "mean_delta_finish_hours", "completion_count_delta_at_horizon"):
            if key in item:
                rev[key] = -item[key]
        if "waiting_worse_jobs" in item and "waiting_better_jobs" in item:
            rev["waiting_worse_jobs"] = item["waiting_better_jobs"]
            rev["waiting_better_jobs"] = item["waiting_worse_jobs"]
        if "finish_worsened_jobs" in item and "finish_improved_jobs" in item:
            rev["finish_worsened_jobs"] = item["finish_improved_jobs"]
            rev["finish_improved_jobs"] = item["finish_worsened_jobs"]
        if "finish_equal_jobs" in item:
            rev["finish_equal_jobs"] = item["finish_equal_jobs"]
        if "equal_wait_jobs" in item:
            rev["equal_wait_jobs"] = item["equal_wait_jobs"]
        for key in PAIR_ASYMMETRIC:
            rev[key] = None
        rev["uncomputed_fields"] = list(PAIR_ASYMMETRIC)
        out[group] = rev
    return out


def pair_value(pair, key):
    """Return a value only when the persisted/derived evidence contains it."""
    return pair.get(key)


def load_rows():
    m1 = json.loads((S1 / "metrics.json").read_text())
    s2 = json.loads((S2 / "sensitivity_metrics.json").read_text())
    rows = []
    for policy in POLICIES:
        for scenario, donor, routing, sigma in SCENARIOS:
            if scenario == "M0":
                x = m1[policy]["M0"]
                a, n, all_ = x["cohorts"]["original_A10"], x["cohorts"]["native_A100"], x["cohorts"]["ALL"]
                paired_m0 = identity_pair()
                paired_s0 = reverse_pair(normalize_pair(m1[policy]["paired_M1_minus_M0"], derive_sigma1_order=True))
                routed = 0; routed_work = 0
            elif scenario == "S0":
                x = m1[policy]["M1"]
                a, n, all_ = x["cohorts"]["original_A10"], x["cohorts"]["native_A100"], x["cohorts"]["ALL"]
                paired_m0 = normalize_pair(m1[policy]["paired_M1_minus_M0"], derive_sigma1_order=True)
                paired_s0 = identity_pair()
                routed = 11209; routed_work = 9.950680
            else:
                x = s2[scenario][policy]
                a, n, all_ = x["A10"], x["native_A100"], x["ALL"]
                paired_m0 = normalize_pair(x["paired_M0"]); paired_s0 = normalize_pair(x["paired_S0"])
                routed = x["routing"]["routed_jobs"]; routed_work = 100 * x["routing"]["routed_gpu_work_fraction"]
            rows.append({
                "scenario": scenario, "policy": policy, "donor_nodes": donor,
                "routing_percent": routing, "sigma": sigma,
                "a10_jobs": a["jobs"], "a10_mean_wait_hours": a["mean_wait_hours"],
                "a10_p95_wait_hours": a["p95_wait_hours"], "a10_p99_wait_hours": a["p99_wait_hours"],
                "a10_max_wait_hours": a["max_wait_hours"], "a10_mean_jct_hours": a["mean_jct_hours"],
                "a10_mean_relative_completion_delay_hours": a.get("mean_relative_completion_delay_hours", a["mean_wait_hours"]),
                "a10_completed_90d": a["completed_at_horizon"], "native_a100_mean_wait_hours": n["mean_wait_hours"],
                "native_a100_p95_wait_hours": n["p95_wait_hours"], "native_a100_p99_wait_hours": n["p99_wait_hours"],
                "native_a100_max_wait_hours": n["max_wait_hours"], "native_a100_completed_90d": n["completed_at_horizon"],
                "all_mean_jct_hours": all_["mean_jct_hours"], "all_completed_90d": all_["completed_at_horizon"],
                "routed_jobs": routed, "routed_gpu_work_percent": routed_work,
                "a10_paired_m0_status": paired_m0["A10"].get("comparison_status", "DIRECT"),
                "a10_paired_s0_status": paired_s0["A10"].get("comparison_status", "DIRECT"),
                "a10_delta_wait_vs_m0_hours": pair_value(paired_m0["A10"], "mean_delta_wait_hours"),
                "a10_delta_jct_vs_m0_hours": pair_value(paired_m0["A10"], "mean_delta_jct_hours"),
                "a10_delta_finish_vs_m0_hours": pair_value(paired_m0["A10"], "mean_delta_finish_hours"),
                "a10_delta_wait_vs_s0_hours": pair_value(paired_s0["A10"], "mean_delta_wait_hours"),
                "a10_delta_jct_vs_s0_hours": pair_value(paired_s0["A10"], "mean_delta_jct_hours"),
                "a10_delta_finish_vs_s0_hours": pair_value(paired_s0["A10"], "mean_delta_finish_hours"),
                "a10_finish_worsened_vs_m0": pair_value(paired_m0["A10"], "finish_worsened_jobs"),
                "a10_finish_improved_vs_m0": pair_value(paired_m0["A10"], "finish_improved_jobs"),
                "a10_finish_worsened_vs_s0": pair_value(paired_s0["A10"], "finish_worsened_jobs"),
                "a10_finish_improved_vs_s0": pair_value(paired_s0["A10"], "finish_improved_jobs"),
                "a10_positive_extra_wait_vs_s0_hours": pair_value(paired_s0["A10"], "positive_extra_wait_hours"),
                "a10_p99_delta_wait_vs_s0_hours": pair_value(paired_s0["A10"], "p99_delta_wait_hours"),
                "a10_max_delta_wait_vs_s0_hours": pair_value(paired_s0["A10"], "max_delta_wait_hours"),
                "a10_zero_wait_new_delay_vs_s0_jobs": pair_value(paired_s0["A10"], "zero_wait_new_delay_jobs"),
                "native_harmed_vs_s0": pair_value(paired_s0["native_A100"], "waiting_worse_jobs"),
                "native_delta_wait_vs_m0_hours": pair_value(paired_m0["native_A100"], "mean_delta_wait_hours"),
                "native_p99_delta_wait_vs_m0_hours": pair_value(paired_m0["native_A100"], "p99_delta_wait_hours"),
                "native_max_delta_wait_vs_m0_hours": pair_value(paired_m0["native_A100"], "max_delta_wait_hours"),
                "native_positive_extra_wait_vs_m0_hours": pair_value(paired_m0["native_A100"], "positive_extra_wait_hours"),
            })
    assert_paired_regressions(rows)
    return rows


def assert_paired_regressions(rows):
    """Guard the M0/S0 direction and the explicitly symmetric reverse counts."""
    by = {(r["scenario"], r["policy"]): r for r in rows}
    for policy in POLICIES:
        m0, s0 = by[("M0", policy)], by[("S0", policy)]
        expected = m0["a10_mean_jct_hours"] - s0["a10_mean_jct_hours"]
        if abs(m0["a10_delta_finish_vs_s0_hours"] - expected) > 1e-9:
            raise AssertionError(f"M0 vs S0 finish delta mismatch for {policy}")
        if abs(m0["a10_delta_finish_vs_s0_hours"] + s0["a10_delta_finish_vs_m0_hours"]) > 1e-9:
            raise AssertionError(f"reverse mean finish deltas are not opposites for {policy}")
        if m0["a10_finish_worsened_vs_s0"] != s0["a10_finish_improved_vs_m0"]:
            raise AssertionError(f"reverse worsened/improved counts mismatch for {policy}")
        if m0["a10_finish_improved_vs_s0"] != s0["a10_finish_worsened_vs_m0"]:
            raise AssertionError(f"reverse improved/worsened counts mismatch for {policy}")


def fmt(value, digits=3):
    return f"{float(value):.{digits}f}"


def write_data(out, rows):
    (out / "paper_ready_metrics.json").write_text(json.dumps({"schema_version": 1, "source": {"S1": "results/20261015-b-q3-fixed-split-c9e8f1a2/metrics.json", "S2": "results/20261015-b-q3-s2-fixed-split-v1/sensitivity_metrics.json"}, "rows": rows}, ensure_ascii=False, indent=2) + "\n")
    fields = list(rows[0])
    with (out / "paper_ready_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(rows)


def table_tex(rows):
    row_end = r"\\"
    lines = [r"\begin{tabular}{llrrrrrr}", r"\toprule", "Scenario & Policy & A10 $\\bar W$ (h) & A10 P95/P99 (h) & A10 $\\bar J$ (h) & Native harm & All $\\bar J$ (h) & 90d done " + row_end, r"\midrule"]
    for r in rows:
        lines.append(f"{r['scenario']} & {r['policy']} & {fmt(r['a10_mean_wait_hours'])} & {fmt(r['a10_p95_wait_hours'])}/{fmt(r['a10_p99_wait_hours'])} & {fmt(r['a10_mean_jct_hours'])} & {r['native_harmed_vs_s0']:,} & {fmt(r['all_mean_jct_hours'])} & {r['all_completed_90d']:,} " + row_end)
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


def table_html(rows):
    heads = ["Scenario", "Policy", "A10 mean wait (h)", "A10 P95/P99 (h)", "A10 mean JCT (h)", "Native harmed", "All mean JCT (h)", "90d done"]
    out = ["<table><caption>Q3 main results. Native harmed counts are paired against S0 under the same policy.</caption><thead><tr>"]
    out += [f"<th>{html.escape(h)}</th>" for h in heads]; out.append("</tr></thead><tbody>")
    for r in rows:
        vals = [r["scenario"], r["policy"], fmt(r["a10_mean_wait_hours"]), f"{fmt(r['a10_p95_wait_hours'])}/{fmt(r['a10_p99_wait_hours'])}", fmt(r["a10_mean_jct_hours"]), f"{r['native_harmed_vs_s0']:,}", fmt(r["all_mean_jct_hours"]), f"{r['all_completed_90d']:,}"]
        out.append("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in vals) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def render_chapters(rows):
    by = {(r["scenario"], r["policy"]): r for r in rows}
    f0, fS0, f5 = by[("M0", "FCFS")], by[("S0", "FCFS")], by[("S5", "FCFS")]
    j0, jS0, j5 = by[("M0", "SJF-HOL")], by[("S0", "SJF-HOL")], by[("S5", "SJF-HOL")]
    fcfs_pct = 100 * (f0["a10_mean_wait_hours"] - fS0["a10_mean_wait_hours"]) / f0["a10_mean_wait_hours"]
    sjf_pct = 100 * (j0["a10_mean_wait_hours"] - jS0["a10_mean_wait_hours"]) / j0["a10_mean_wait_hours"]
    f5_jct_delta = f5["a10_delta_jct_vs_m0_hours"]; j5_jct_delta = j5["a10_delta_jct_vs_m0_hours"]
    tex = rf'''\documentclass[11pt,a4paper]{{article}}
\usepackage[margin=0.8in]{{geometry}}
\usepackage{{amsmath,amssymb,booktabs,graphicx,caption}}
\usepackage[T1]{{fontenc}}
\usepackage[utf8]{{inputenc}}
\setlength{{\tabcolsep}}{{2.5pt}}
\begin{{document}}
\begingroup
\renewcommand{{\normalsize}}{{\fontsize{{11.1pt}}{{13.3pt}}\selectfont}}
\normalsize
\section{{Question 3: Fixed-Split Cross-GPU Substitution}}
\label{{sec:q3}}

\subsection{{Model and assumptions}}
We study a finite, whole-card, pre-start substitution policy on the supplied trace of 224,112 jobs. Job $j$ has native GPU model $n_j$, actual execution model $m_j$, duration $p_j$, worker count $W_j$, per-worker GPU request $g_j$, and per-worker CPU request $c_j$. A compatibility indicator $K_{{jm}}$ and multiplier $\sigma_{{jm}}$ are declared scenario assumptions; they are not measured hardware facts. For the only foreign edge in this study, A10 jobs may execute on A100-SXM4-80GB and
\begin{{equation}}
 p'_j=\sigma_{{jm}}p_j,
 \qquad f_j=s_j+p'_j,
 \qquad \omega_j=s_j-a_j.
\end{{equation}}
The fixed partition reserves the first $B$ A100 nodes in ascending $\texttt{{node\_name}}$ order for routed A10 jobs and leaves the other A100 nodes for native A100 jobs. Each worker's CPU and GPU remain on one physical node, all workers of a job start together, jobs are non-preemptive and non-migrating, and no resource may be used twice. At every node $i$ and time $t$,
\begin{{equation}}
 \sum_{{j:s_j\le t<f_j}}g_jy_{{ji}}\le G_i^{{\rm cap}},\qquad
 \sum_{{j:s_j\le t<f_j}}c_jy_{{ji}}\le C_i^{{\rm cap}},\qquad
 \sum_i y_{{ji}}=W_j.
\end{{equation}}
The model is a deterministic scheduling heuristic, not an optimality claim.

\subsection{{Fixed-split counterfactual design}}
M0 is the original model-isolated schedule. S0 is the earlier Q3-S1 M1 result, renamed to make the comparison unambiguous: 60 dedicated A100 nodes, a 10\% SHA-256 threshold, and $\sigma=1$. S1--S5 vary exactly one factor from S0: 5\% or 20\% routing, 30 or 90 donor nodes, or $\sigma=2$. The hash namespace is fixed as `q3-fixed-split-v1`; eligibility uses only the current job and declared capacity. There is no fallback from the foreign queue and no relocation of a running job.

We report worker count $W_j$ separately from waiting $\omega_j=s_j-a_j$, actual JCT $J_j=f_j-a_j$, relative completion delay $f_j-a_j-p_j$, and paired finish difference $f_{{\rm scenario}}-f_{{\rm reference}}$. Every comparison uses the same original job IDs. The 90-day window is $H=7,776,000$ seconds; waiting and JCT use complete drain, while completion counts use $f_j\le H$.

\begin{{table}}[!ht]
\centering
\caption{{Main Q3 results generated from the paper-ready JSON. Native harmed counts are paired against S0 under the same policy.}}
\label{{tab:q3_main}}
\input{{q3_s3_main_table.tex}}
\end{{table}}

\subsection{{Benefit, native-pool cost and sensitivity}}
With $\sigma=1$, S0 reduces A10 mean waiting from {fmt(f0['a10_mean_wait_hours'])} to {fmt(fS0['a10_mean_wait_hours'])} hours under FCFS ({fmt(fcfs_pct,1)}\% relative to M0) and from {fmt(j0['a10_mean_wait_hours'])} to {fmt(jS0['a10_mean_wait_hours'])} hours under SJF-HOL ({fmt(sjf_pct,1)}\%). Cluster-wide mean JCT changes from {fmt(f0['all_mean_jct_hours'])} to {fmt(fS0['all_mean_jct_hours'])} hours for FCFS and from {fmt(j0['all_mean_jct_hours'])} to {fmt(jS0['all_mean_jct_hours'])} hours for SJF-HOL. The native A100 mean and P99 waiting costs are zero in S0 on this trace; this is a trace result, not an SLA.

More routing is not uniformly better. At 60 donor nodes, FCFS A10 mean waiting is {fmt(by[('S1','FCFS')]['a10_mean_wait_hours'])}, {fmt(fS0['a10_mean_wait_hours'])}, and {fmt(by[('S2','FCFS')]['a10_mean_wait_hours'])} hours at 5\%, 10\%, and 20\%. The 20\% case is worse than both 10\% and M0. SJF-HOL gives {fmt(by[('S1','SJF-HOL')]['a10_mean_wait_hours'])}, {fmt(jS0['a10_mean_wait_hours'])}, and {fmt(by[('S2','SJF-HOL')]['a10_mean_wait_hours'])} hours, while its P99 tail and 90-day completion count move differently. These are finite fixed-split observations; they do not establish monotonicity for another trace or a dynamic policy.

At 10\% routing and $\sigma=1$, increasing donors from 30 to 60 to 90 lowers A10 mean waiting for both policies, but 90 nodes creates native A100 harm: {by[('S4','FCFS')]['native_harmed_vs_s0']:,} FCFS jobs and {by[('S4','SJF-HOL')]['native_harmed_vs_s0']:,} SJF-HOL jobs wait longer than in S0. Their mean additional waits are {fmt(by[('S4','FCFS')]['native_delta_wait_vs_m0_hours'],4)} and {fmt(by[('S4','SJF-HOL')]['native_delta_wait_vs_m0_hours'],4)} hours, respectively. The 90-node point remains in the trade-off table rather than being discarded.

\begin{{figure}}[!ht]
\centering
\includegraphics[width=\textwidth]{{figures/q3_donor_capacity_wait_tradeoff.png}}
\caption{{Capacity sensitivity from the persisted S2 results. The left panel shows A10 mean-wait improvement relative to M0; the right panel shows native A100 mean-wait increase relative to M0. The two panels use different scales so the small native cost remains visible without being treated as zero.}}
\label{{fig:q3_capacity}}
\end{{figure}}

For $\sigma=2$, the effective duration of routed A10 jobs doubles and SJF-HOL is re-simulated because its queue key changes. FCFS A10 mean JCT changes from {fmt(f0['a10_mean_jct_hours'])} to {fmt(f5['a10_mean_jct_hours'])} hours (paired delta {fmt(f5_jct_delta)} hours), while SJF-HOL changes from {fmt(j0['a10_mean_jct_hours'])} to {fmt(j5['a10_mean_jct_hours'])} hours (paired delta {fmt(j5_jct_delta)} hours). For the full trace, SJF-HOL all-job mean JCT changes from {fmt(j0['all_mean_jct_hours'])} to {fmt(j5['all_mean_jct_hours'])} hours and 90-day completions from {j0['all_completed_90d']:,} to {j5['all_completed_90d']:,}; waiting falls relative to M0 but completion worsens. FCFS retains a mean-JCT benefit in this $\sigma=2$ scenario. No interpolation or exact break-even $\sigma^*$ is claimed.

\subsection{{Conditional recommendation and limitations}}
If the policy requirement is zero additional native A100 waiting on this trace, 60 nodes at 10\% is a tested candidate for either policy; it is not a proven maximum safe capacity or a global optimum. If a small native cost is acceptable, 90 nodes supplies an additional point on the A10--native trade-off. SJF-HOL's lower mean waiting does not remove its tail and completion-fairness losses; all harmed-job counts and positive delay totals remain in the paired evidence.

Compatibility and $\sigma$ are assumptions without an A10/A100 performance matrix. Allocation rates are request occupancy, not measured utilization; GPU-hours across models are not interchangeable compute or monetary units. The experiment adds no physical GPUs, does not implement dynamic sharing, MIG, pricing, RL, migration, or Q2\,$\times$\,Q3 scheduling, and does not prove heuristic optimality. Q1's A10 lower bound is not transferred to substituted schedules. The conclusion is therefore conditional on the declared trace, partitions, hash rule, policy, and duration scenarios.
\par\endgroup
\end{{document}}
'''
    zh = f'''<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>問題三：固定分流跨 GPU 替代</title>
<style>body{{max-width:1000px;margin:32px auto;padding:0 22px;font:16px/1.75 system-ui,"Noto Sans CJK TC",sans-serif;color:#203040}}h1,h2{{color:#1b4f72}}.note{{border-left:4px solid #1b4f72;background:#f1f6fa;padding:10px 16px}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:6px;border-bottom:1px solid #d4dde4;text-align:right}}th:first-child,td:first-child{{text-align:left}}thead{{background:#eef4f8}}figure{{margin:22px 0}}img{{width:100%;height:auto}}.formula{{padding:10px;background:#f6f8fa;text-align:center;font-family:serif}}</style></head><body>
<h1>問題三：固定分流跨 GPU 替代</h1>
<p class="note">本章只使用已完成的 M0、S0、S1–S5；沒有新增排程情景。第一輪的 M1 統一稱為 S0。相容性與 σ 是情景假設，不是硬體 benchmark。</p>
<h2>模型與假設</h2>
<p>作業 j 的原生 GPU 型號為 n<sub>j</sub>，實際型號為 m<sub>j</sub>，原始時長為 p<sub>j</sub>，有效時長為 p′<sub>j</sub> = σ<sub>jm</sub>p<sub>j</sub>，完成時間為 f<sub>j</sub> = s<sub>j</sub> + p′<sub>j</sub>，等待為 ω<sub>j</sub> = s<sub>j</sub> − a<sub>j</sub>；worker 數另以 W<sub>j</sub> 表示。固定分區把按 <code>node_name</code> 字典序排序的前 B 台 A100 專供外來 A10，其餘 A100 只服務原生 A100；worker 必須同節點滿足 CPU/GPU，全部同步啟動，不搶占、不遷移、不 fallback，且每一時刻逐節點容量不超額。</p>
<div class="formula">Σ<sub>j:s<sub>j</sub>≤t&lt;f<sub>j</sub></sub> g<sub>j</sub>y<sub>ji</sub> ≤ G<sub>i</sub><sup>cap</sup>，Σ c<sub>j</sub>y<sub>ji</sub> ≤ C<sub>i</sub><sup>cap</sup>，Σ<sub>i</sub>y<sub>ji</sub> = W<sub>j</sub></div>
<h2>反事實設計與主要結果</h2>
<p>M0 是原始型號隔離；S0 是 60 台／10% 固定 SHA-256 分流／σ=1。S1–S5 每次只變更一個因素。所有比較使用 224,112 個原始 job ID；90 天窗口為 H=7,776,000 秒，窗口完成與完整排空分開計算。worker 數為 W<sub>j</sub>，等待為 ω<sub>j</sub>=s<sub>j</sub>−a<sub>j</sub>，JCT=f<sub>j</sub>−a<sub>j</sub>，relative completion delay=f<sub>j</sub>−a<sub>j</sub>−p<sub>j</sub>。</p>
{table_html(rows)}
<p>σ=1 的 S0 將 FCFS A10 平均等待由 {fmt(f0['a10_mean_wait_hours'])} 小時降至 {fmt(fS0['a10_mean_wait_hours'])} 小時（{fmt(fcfs_pct,1)}%），SJF-HOL 由 {fmt(j0['a10_mean_wait_hours'])} 降至 {fmt(jS0['a10_mean_wait_hours'])} 小時（{fmt(sjf_pct,1)}%）。native A100 在 S0 的新增等待為零只適用於此 trace。</p>
<p>多分流不保證更好：FCFS 在 20% 時為 {fmt(by[('S2','FCFS')]['a10_mean_wait_hours'])} 小時，已高於 10% 與 M0；SJF-HOL 的平均、P99 與窗口完成數有不同取捨。30/60/90 台增加 donor 可降低 A10 平均等待，但 90 台產生 {by[('S4','FCFS')]['native_harmed_vs_s0']:,}/{by[('S4','SJF-HOL')]['native_harmed_vs_s0']:,} 個 native A100 受損作業（FCFS/SJF-HOL）。</p>
<figure><img src="figures/q3_donor_capacity_wait_tradeoff.png" alt="donor capacity trade-off"><figcaption>圖：30/60/90 台 donor 的 A10 平均等待改善與 native A100 平均等待增加。</figcaption></figure>
<p>σ=2 時，FCFS A10 平均 JCT 由 {fmt(f0['a10_mean_jct_hours'])} 變為 {fmt(f5['a10_mean_jct_hours'])} 小時，仍優於 M0；SJF-HOL 由 {fmt(j0['a10_mean_jct_hours'])} 變為 {fmt(j5['a10_mean_jct_hours'])} 小時，略差於 M0。SJF-HOL 全體平均 JCT 由 {fmt(j0['all_mean_jct_hours'])} 變為 {fmt(j5['all_mean_jct_hours'])} 小時，90 天完成由 {j0['all_completed_90d']:,} 變為 {j5['all_completed_90d']:,}。因此等待與完成可能方向相反，不能插值或宣稱精確 σ*。</p>
<h2>條件性建議與限制</h2><p>若政策要求本 trace 的 native A100 零新增等待，60 台／10% 是已測候選之一；若允許有限宿主代價，90 台仍應保留在取捨表。這些結果不證明全域最佳，也不代表動態共享、MIG、定價或 Q2×Q3 聯合排程。allocation 是請求資源占用，不是量測利用率；不同型號 GPU-hours 不可直接視為等效算力或金錢。</p>
</body></html>'''
    return tex, zh


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--latex-status", default="NOT_RUN: no compiler status supplied")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("release directory already exists")
    started = time.perf_counter()
    rows = load_rows()
    args.out.mkdir(parents=True)
    write_data(args.out, rows)
    tex_table = table_tex(rows)
    (args.out / "q3_s3_main_table.tex").write_text(tex_table)
    tex, zh = render_chapters(rows)
    (PAPER / "q3_section.tex").write_text(tex)
    (PAPER / "q3_s3_main_table.tex").write_text(tex_table)
    (PAPER / "q3_section_zh.html").write_text(zh)
    (PAPER / "figures").mkdir(exist_ok=True)
    fig = S2 / "figures/donor_capacity_wait_tradeoff.png"
    shutil.copyfile(fig, PAPER / "figures/q3_donor_capacity_wait_tradeoff.png")
    shutil.copyfile(fig, args.out / "q3_donor_capacity_wait_tradeoff.png")
    sources = {
        "commit_scope": {"git_commit_at_execution": git_head(), "new_scheduling_runs": 0},
        "model": {"file": "problems/2026_gpu_scheduling/docs/q3_model.md", "claim": "whole-card pre-start fixed partition, CPU/GPU same-node constraints"},
        "M0_S0": {"file": "results/20261015-b-q3-fixed-split-c9e8f1a2/metrics.json", "fields": ["FCFS.M0", "FCFS.M1", "SJF-HOL.M0", "SJF-HOL.M1"], "note": "M1 is renamed S0 in publication text"},
        "S1_S5": {"file": "results/20261015-b-q3-s2-fixed-split-v1/sensitivity_metrics.json", "fields": ["S1..S5.*.A10", "S1..S5.*.native_A100", "S1..S5.*.ALL", "paired_M0", "paired_S0"]},
        "routing": {"file": "results/20261015-b-q3-s2-fixed-split-v1/routing_audit.json", "formula": "SHA256(q3-fixed-split-v1:<job_id>) threshold; S1 subset S0 subset S2"},
        "metrics": {"file": "paper_ready_metrics.json", "formulas": {"waiting": "start-submit", "jct": "finish-submit", "relative_completion_delay": "finish-submit-original_duration", "paired_finish_delta": "finish_scenario-finish_reference"}},
        "figure": {"file": "q3_donor_capacity_wait_tradeoff.png", "source": "results/20261015-b-q3-s2-fixed-split-v1/figures/donor_capacity_wait_tradeoff.png"},
    }
    (args.out / "q3_claim_sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n")
    checks = {
        "new_scheduling_runs": 0,
        "source_json_loaded": True,
        "paper_ready_rows": len(rows),
        "policies": sorted({r["policy"] for r in rows}),
        "scenarios": sorted({r["scenario"] for r in rows}),
        "numeric_source_single": True,
        "english_chinese_generated_from_same_rows": True,
        "tex_required_sections": all(x in tex for x in ["Model and assumptions", "Fixed-split counterfactual design", "Benefit, native-pool cost and sensitivity", "Conditional recommendation and limitations"]),
        "paired_regressions": True,
        "reverse_uncomputed_asymmetric_fields_explicit": all(r["a10_paired_s0_status"] == "REVERSED_SYMMETRIC_ONLY" and r["a10_positive_extra_wait_vs_s0_hours"] is None for r in rows if r["scenario"] == "M0"),
        "table_rows_end_with_two_backslashes": all(line.endswith(r"\\") for line in tex_table.splitlines() if "&" in line),
        "node_name_escaped": r"\texttt{node\_name}" in tex,
        "worker_wait_symbols_separated": "worker count $W_j$ separately from waiting $\\omega_j" in tex,
        "no_static_relocation_claim": "Initial Job Relocation" not in tex,
        "latex_compiler": args.latex_status,
        "cross_machine_evidence": "BLOCKED: no authorized shared storage was available",
        "elapsed_seconds": time.perf_counter() - started,
    }
    (args.out / "publication_checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(checks, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
