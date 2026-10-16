#!/usr/bin/env python3
"""Create compact Q3-S2 tables and the donor-capacity figure."""
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt

POLICIES = ("FCFS", "SJF-HOL")


def load(path):
    return json.loads((path / "sensitivity_metrics.json").read_text())


def row(scenario, policy, x):
    a = x["A10"]; n = x["native_A100"]; all_ = x["ALL"]; p = x["physical"]
    foreign = p["A100-foreign"]
    return {
        "Scenario": scenario, "Policy": policy, "A10 mean wait (h)": a["mean_wait_hours"],
        "A10 P95/P99 wait (h)": f"{a['p95_wait_hours']:.3f}/{a['p99_wait_hours']:.3f}",
        "A10 mean JCT (h)": a["mean_jct_hours"], "All completed @90d": all_["completed_at_horizon"],
        "Native A100 mean/P99 wait (h)": f"{n['mean_wait_hours']:.3f}/{n['p99_wait_hours']:.3f}",
        "Routed jobs": x["routing"]["routed_jobs"], "Routed GPU-work (%)": 100*x["routing"]["routed_gpu_work_fraction"],
        "Native harmed jobs (vs S0)": x["paired_S0"]["native_A100"]["waiting_worse_jobs"],
        "A10 harmed jobs (vs S0)": x["paired_S0"]["A10"]["finish_worsened_jobs"],
        "All mean JCT (h)": all_["mean_jct_hours"],
        "Donor GPU/CPU allocation (%)": f"{100*foreign['gpu_allocation_rate_at_horizon']:.3f}/{100*foreign['cpu_allocation_rate_at_horizon']:.3f}",
        "Wall (s)": x["wall_seconds"],
    }


def markdown_table(rows, columns):
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for r in rows:
        vals=[]
        for c in columns:
            v=r[c]
            vals.append(f"{v:.6f}" if isinstance(v,float) else str(v))
        out.append("| " + " | ".join(vals) + " |")
    return "\n".join(out)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--results", type=Path, required=True)
    args=p.parse_args()
    data=load(args.results)
    scenarios=("S1","S2","S3","S4","S5")
    rows=[row(s,pol,data[s][pol]) for s in scenarios for pol in POLICIES]
    a_cols=["Scenario","Policy","A10 mean wait (h)","A10 P95/P99 wait (h)","A10 mean JCT (h)","All completed @90d","Native A100 mean/P99 wait (h)"]
    b_cols=["Scenario","Policy","Routed jobs","Routed GPU-work (%)","Native harmed jobs (vs S0)","A10 harmed jobs (vs S0)","All mean JCT (h)","Donor GPU/CPU allocation (%)","Wall (s)"]
    (args.results/"table_q3_s2_a.md").write_text("# Table Q3-S2-A\n\n"+markdown_table(rows,a_cols)+"\n",encoding="utf-8")
    (args.results/"table_q3_s2_b.md").write_text("# Table Q3-S2-B\n\n"+markdown_table(rows,b_cols)+"\n",encoding="utf-8")
    (args.results/"paired_comparisons.json").write_text(json.dumps({s:{pol:{"vs_M0":data[s][pol]["paired_M0"],"vs_S0":data[s][pol]["paired_S0"]} for pol in POLICIES} for s in scenarios},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    figdir=args.results/"figures"; figdir.mkdir(exist_ok=True)
    donor=[30,60,90]; lookup={30:"S3",60:"S0",90:"S4"}
    # S0 values are read from the versioned S1 result metrics, while S3/S4 use S2.
    s1=json.loads((Path("results/20261015-b-q3-fixed-split-c9e8f1a2")/"metrics.json").read_text())
    fig,axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
    for pol,color in zip(POLICIES,("#1565c0","#c62828")):
        improvement=[]; native_loss=[]
        for n in donor:
            if n==60:
                x=s1[pol]["M1"]; b=s1[pol]["M0"]
                improvement.append(b["cohorts"]["original_A10"]["mean_wait_hours"]-x["cohorts"]["original_A10"]["mean_wait_hours"])
                native_loss.append(x["cohorts"]["native_A100"]["mean_wait_hours"]-b["cohorts"]["native_A100"]["mean_wait_hours"])
            else:
                x=data[lookup[n]][pol]; improvement.append(-x["paired_M0"]["A10"]["mean_delta_wait_hours"]); native_loss.append(x["paired_M0"]["native_A100"]["mean_delta_wait_hours"])
        axes[0].plot(donor,improvement,marker="o",label=pol,color=color)
        axes[1].plot(donor,native_loss,marker="o",label=pol,color=color)
    axes[0].axhline(0,color="black",linewidth=.8); axes[1].axhline(0,color="black",linewidth=.8)
    axes[0].set(xlabel="Dedicated donor A100 nodes",ylabel="A10 mean-wait improvement (hours)")
    axes[1].set(xlabel="Dedicated donor A100 nodes",ylabel="Native A100 mean-wait increase (hours)")
    axes[0].legend(); fig.suptitle("Q3 fixed split: donor capacity sensitivity")
    fig.savefig(figdir/"donor_capacity_wait_tradeoff.png",dpi=180)
    plt.close(fig)


if __name__ == "__main__": main()
