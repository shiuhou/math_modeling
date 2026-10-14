#!/usr/bin/env python3
"""Reproduce the original four-panel Q1 figure with audited data-derived values.

Q2/Q3 archived table figures are opt-in and visibly marked as unverified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

PROBLEM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROBLEM / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
from gpu_scheduling.q1 import ccdf, gini, load_data, lorenz, top_share, demand_timeline


def paper_reference_figures(nodes, jobs, stats, pools, out):
    """Render archived table values; never present them as new experiment results."""
    source = PROBLEM / "references/paper_metrics.reference.json"
    ref = json.loads(source.read_text())
    original = PROBLEM / ref['original_git_path']
    if hashlib.sha256(original.read_bytes()).hexdigest() != ref['source_sha256']:
        raise ValueError('Archived paper source hash differs')
    rows = ref['q2']
    labels = [r['policy'] for r in rows]
    x = np.arange(len(rows))
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.3), layout='constrained')
    for key, label, color in [('mean_h','Mean','#1b4f72'),('p95_h','P95','#e67e22'),('max_h','Maximum','#c0392b')]:
        axes[0].plot(x, [r[key] for r in rows], 'o-', label=label, color=color)
    axes[0].set(yscale='log', ylabel='Waiting time (hours)', title='(a) Archived overall waiting times')
    axes[0].set_xticks(x, labels, rotation=55, ha='right', fontsize=8)
    axes[0].legend(fontsize=8)
    for offset, key, label in [(-.18,'a100_mean_h','A100'),(.18,'gs1_mean_h','GPU-s1')]:
        axes[1].bar(x+offset, [r[key] for r in rows], width=.36, label=label)
    axes[1].set(ylabel='Mean wait (hours; zeros retained)', title='(b) Policy and placement comparison')
    axes[1].set_xticks(x, labels, rotation=55, ha='right', fontsize=8)
    axes[1].legend(fontsize=8)
    for row in rows:
        axes[2].scatter(row['a10_mean_h'],row['max_h'],s=25)
        axes[2].annotate(row['policy'],(row['a10_mean_h'],row['max_h']),fontsize=7,xytext=(3,3),textcoords='offset points')
    axes[2].set(xlabel='A10 mean wait (hours)',ylabel='Cluster maximum wait (hours)', title='(c) Archived delay trade-off')
    for ax in axes: ax.grid(alpha=.2)
    fig.suptitle('Archived Q2 claims - verification pending (NOT_RUN)',fontsize=12)
    fig.savefig(out/'fig2_q2_scheduling.pdf'); plt.close(fig)

    fig, axes = plt.subplots(2,2,figsize=(13,8),layout='constrained')
    horizon = stats['horizon_seconds']
    bins = np.r_[np.arange(0,horizon,86400),horizon]
    demand_checks = {}
    for model,color in [('A10','#c0392b'),('A100-SXM4-80GB','#1b4f72')]:
        sub=jobs[jobs.gpu_model==model]
        edges,values,area=demand_timeline(sub.submit_time,sub.duration,sub.total_gpu,horizon)
        integral=np.r_[0,np.cumsum(values*np.diff(edges))]
        # Piecewise-linear cumulative area gives exact overlap in every bin.
        averages=np.diff(np.interp(bins,edges,integral))/np.diff(bins)
        capacity=int(nodes.loc[nodes.gpu_model==model,'gpu_capacity_num'].sum())
        axes[0,0].stairs(averages,bins/86400,color=color,label=f'{model}: immediate start')
        axes[0,0].axhline(capacity,color=color,linestyle='--',label=f'{model}: capacity {capacity:,}')
        demand_checks[model]={'mean':area/horizon,'capacity':capacity,'peak':int(values.max())}
    axes[0,0].set(xlabel='Trace-relative day',ylabel='GPUs (exact daily overlap average)',title='(a) Counterfactual demand, not allocation')
    axes[0,0].legend(fontsize=8)
    mig=ref['q3_mig']
    for key,label in [('mig2_mean_h','MIG-2x'),('mig3_mean_h','MIG-3x')]:
        axes[0,1].plot(mig['nodes'],[np.nan if v is None else v for v in mig[key]],'o-',label=label)
    axes[0,1].set(xlabel='Converted A100 nodes',ylabel='A10 mean wait (hours)',title='(b) Archived MIG claims - NOT_RUN')
    axes[0,1].legend(fontsize=8)
    pricing=ref['q3_pricing']; ax=axes[1,0]; twin=ax.twinx()
    ax.plot(pricing['discount_pct'],pricing['mean_h'],'o-',color='#1b4f72',label='Mean wait (h)')
    ax.plot(pricing['discount_pct'],pricing['migration_pct'],'s--',color='#27ae60',label='Migrated jobs (%)')
    twin.plot(pricing['discount_pct'],pricing['revenue_million_usd'],'d:',color='#c0392b',label='Revenue ($M)')
    ax.set(xlabel='Discount (%); last two surcharges 10%, 15%',ylabel='Hours / percent',title='(c) Archived pricing claims - NOT_RUN')
    twin.set_ylabel('Revenue (million USD)')
    lines= ax.get_lines()+twin.get_lines(); ax.legend(lines,[l.get_label() for l in lines],fontsize=8)
    axes[1,1].bar(pools.gpu_model,pools.rho_gpu,color='#2e86c1')
    axes[1,1].axhline(1,linestyle='--',color='#c0392b')
    axes[1,1].tick_params(axis='x',rotation=35,labelsize=8)
    axes[1,1].set(ylabel='Lifetime work / exact-window capacity',title='(d) Q1 data context, not utilization')
    for ax in axes.flat: ax.grid(alpha=.2)
    fig.suptitle('Q3 context: data-derived (a,d); archived and unverified (b,c)',fontsize=12)
    fig.savefig(out/'fig3_q3_imbalance.pdf'); plt.close(fig)
    (out/'paper_reference_figures.json').write_text(json.dumps({
        'historical_claims':'NOT_RUN','reference_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'counterfactual_demand':demand_checks,'interpolated_metrics':False,
        'files':{n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in ['fig2_q2_scheduling.pdf','fig3_q3_imbalance.pdf']}
    },indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PROBLEM / "data/raw")
    parser.add_argument("--results", type=Path, required=True, help="Recomputed Q1 output directory")
    parser.add_argument("--out", type=Path, required=True, help="New local figure directory")
    parser.add_argument("--paper-reference", action="store_true", help="Also render visibly unverified Q2/Q3 archived table figures")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output exists; choose a new directory")
    nodes, jobs, hashes = load_data(args.data)
    stats = json.loads((args.results / "q1_results.json").read_text(encoding="utf-8"))
    if hashes != stats["input_sha256"]:
        parser.error("Q1 results and plotting inputs have different byte hashes")
    pools = pd.read_csv(args.results / "pool_summary.csv")
    phases = pd.read_csv(args.results / "relative_24h_phase.csv")
    if set(pools.gpu_model) != set(jobs.gpu_model):
        parser.error("Pool summary does not match input GPU models")
    args.out.mkdir(parents=True, exist_ok=False)

    # Keep the supplied figure's typography, palette, four-panel layout and
    # dimensional labels; calculate every plotted statistic from this run.
    plt.rcParams["font.sans-serif"] = "DejaVu Sans"
    plt.rcParams["axes.edgecolor"] = "#333333"
    plt.rcParams["axes.linewidth"] = 0.8
    palette = ["#1b4f72", "#2e86c1", "#c0392b", "#e67e22", "#27ae60", "#8e44ad"]
    short = {"A100-SXM4-80GB": "A100-80G", "A800-SXM4-80GB": "A800-80G",
             "GPU-series-1": "GPU-s1", "GPU-series-2": "GPU-s2"}
    models = pools.gpu_model.tolist()
    names = [short.get(model, model) for model in models]
    fig = plt.figure(figsize=(13, 9.5), dpi=200)
    gs = gridspec.GridSpec(2, 2, hspace=.34, wspace=.30)

    ax1 = fig.add_subplot(gs[0, 0])
    x, width = np.arange(len(models)), .25
    ax1.bar(x-width, pools.capacity_share*100, width=width, label="GPU capacity share (%)", color="#2e86c1", alpha=.9)
    ax1.bar(x, pools.job_share*100, width=width, label="Job arrival share (%)", color="#27ae60", alpha=.9)
    ax1.bar(x+width, pools.work_share*100, width=width, label="Lifetime GPU-work share (%)", color="#c0392b", alpha=.9)
    ax1.set_xticks(x, names, fontsize=9)
    ax1.set_ylabel("Percentage share (%)", fontsize=10)
    ax1.set_ylim(0, max(pools[["capacity_share", "job_share", "work_share"]].max())*100*1.25)
    ax1.grid(axis="y", linestyle="--", alpha=.4)
    twin = ax1.twinx()
    twin.plot(x, pools.rho_gpu, color="#d35400", marker="o", linewidth=2.2, markersize=7, label="Lifetime work / window capacity")
    twin.axhline(1, color="#7f8c8d", linestyle=":", linewidth=1.2)
    twin.set_ylabel("Work / capacity over exact trace window", color="#d35400", fontsize=9)
    twin.set_ylim(0, pools.rho_gpu.max()*1.25)
    for i, value in enumerate(pools.rho_gpu):
        twin.annotate(f"{value:.2f}x", (i, value), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8, color="#a04000")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = twin.get_legend_handles_labels()
    ax1.legend(lines1+lines2, labels1+labels2, loc="upper right", fontsize=7.4)
    ax1.set_title("(a) GPU-model supply and submitted lifetime work", fontsize=11, fontweight="bold", pad=8)

    ax2 = fig.add_subplot(gs[0, 1])
    x_lorenz, y_lorenz = lorenz(jobs.gpu_seconds)
    indices = np.unique(np.r_[0, np.linspace(0, len(x_lorenz)-1, 1000).astype(int)])
    ax2.plot(x_lorenz[indices]*100, y_lorenz[indices]*100, color="#c0392b", linewidth=2.5,
             label=f"All jobs (Gini={gini(jobs.gpu_seconds):.4f})")
    for model, color, style in [("A10", "#1b4f72", "--"), ("A100-SXM4-80GB", "#2e86c1", "-."), ("GPU-series-1", "#27ae60", ":")]:
        sub = jobs[jobs.gpu_model == model]
        if sub.empty:
            continue
        xl, yl = lorenz(sub.gpu_seconds)
        ix = np.unique(np.r_[0, np.linspace(0, len(xl)-1, 500).astype(int)])
        ax2.plot(xl[ix]*100, yl[ix]*100, color=color, linestyle=style, linewidth=1.8,
                 label=f"{short.get(model, model)} (Gini={gini(sub.gpu_seconds):.3f})")
    ax2.plot([0, 100], [0, 100], color="#7f8c8d", linestyle="--", linewidth=1, label="Equality")
    annotations = []
    for fraction in [.05, .01]:
        count, share = top_share(jobs.gpu_seconds, fraction)
        ax2.scatter(100*(1-count/len(jobs)), 100*(1-share), color="#c0392b", zorder=5, s=40)
        annotations.append(f"Top {fraction*100:g}% ({count:,} jobs): {share*100:.2f}% work")
    ax2.text(.40, .30, "\n".join(annotations), transform=ax2.transAxes, fontsize=8,
             bbox=dict(boxstyle="round,pad=0.3", facecolor="#fdedec", edgecolor="#c0392b", alpha=.9))
    ax2.set(xlabel="Cumulative share of jobs (%)", ylabel="Cumulative share of GPU work (%)", xlim=(0, 100), ylim=(0, 100))
    ax2.grid(True, linestyle="--", alpha=.4)
    ax2.legend(loc="upper left", fontsize=8)
    ax2.set_title("(b) Concentration of full-lifetime GPU work", fontsize=11, fontweight="bold", pad=8)

    ax3 = fig.add_subplot(gs[1, 0])
    for model, color, marker, style in [("ALL", "#1b4f72", "o", "-"), ("A10", "#c0392b", "s", "--"), ("A100-SXM4-80GB", "#2e86c1", "^", ":")]:
        frame = phases[phases.gpu_model == model].sort_values("relative_phase_hour")
        ax3.plot(frame.relative_phase_hour, frame.jobs_per_exposed_hour, color=color, marker=marker,
                 linestyle=style, linewidth=1.8, markersize=4, label=short.get(model, "All models" if model == "ALL" else model))
    overall = phases[phases.gpu_model == "ALL"]
    peak = overall.loc[overall.jobs_per_exposed_hour.idxmax()]
    trough = overall.loc[overall.jobs_per_exposed_hour.idxmin()]
    ax3.annotate(f"Phase {int(peak.relative_phase_hour)}: {peak.jobs_per_exposed_hour:.1f} jobs/h\n"
                 f"Peak/trough: {peak.jobs_per_exposed_hour/trough.jobs_per_exposed_hour:.2f}x",
                 xy=(peak.relative_phase_hour, peak.jobs_per_exposed_hour), xytext=(.50, .92), textcoords="axes fraction",
                 arrowprops=dict(arrowstyle="->", color="#1b4f72", lw=1.2), fontsize=8.5, va="top")
    ax3.set_xlabel("Relative trace phase (hour modulo 24; no timezone)", fontsize=9)
    ax3.set_ylabel("Arrivals per exposed phase-hour (t > 0)", fontsize=9)
    ax3.set_xticks(range(0, 24, 2))
    ax3.set_ylim(0, overall.jobs_per_exposed_hour.max()*1.3)
    ax3.grid(True, linestyle="--", alpha=.4)
    ax3.legend(loc="upper left", fontsize=8)
    ax3.set_title("(c) Arrival variation by relative 24-hour phase", fontsize=11, fontweight="bold", pad=8)

    ax4 = fig.add_subplot(gs[1, 1])
    ccdf_checks = {}
    for index, model in enumerate(models):
        values = jobs.loc[jobs.gpu_model == model, "duration"]
        durations, probability = ccdf(values)
        positive = probability > 0  # The terminal zero cannot appear on a log axis.
        # Show the last positive plateau up to the maximum duration; the drop
        # to zero at that maximum is outside the logarithmic probability axis.
        plot_durations = np.r_[durations[positive], durations[-1]]
        plot_probability = np.r_[probability[positive], probability[positive][-1]]
        ax4.step(plot_durations/3600, plot_probability, where="post", label=short.get(model, model),
                 color=palette[index % len(palette)], linewidth=1.5)
        ccdf_checks[model] = {"unique_durations": len(durations), "ties_grouped": True,
                              "terminal_probability": float(probability[-1])}
    ax4.set_xscale("log")
    ax4.set_yscale("log")
    ax4.axvline(stats["horizon_hours"], color="#7f8c8d", linestyle="--", linewidth=1.2, label="Exact observation window")
    ax4.set_xlabel("Job duration (hours, log scale)", fontsize=10)
    ax4.set_ylabel("Strict empirical P(duration > d), log scale", fontsize=9)
    ax4.grid(True, which="both", linestyle="--", alpha=.35)
    ax4.legend(loc="lower left", fontsize=8, ncol=2)
    ax4.set_title("(d) Job-duration CCDF (no fitted tail law)", fontsize=11, fontweight="bold", pad=8)

    fig.savefig(args.out / "fig1_data_patterns.pdf", bbox_inches="tight")
    fig.savefig(args.out / "fig1_data_patterns.png", bbox_inches="tight")
    plt.close(fig)
    record = {"scope": "Q1 only", "input_sha256": hashes, "q1_results_sha256": hashlib.sha256((args.results / "q1_results.json").read_bytes()).hexdigest(),
              "style": "Original four-panel layout, DejaVu Sans, supplied palette",
              "lorenz_origin": [float(x_lorenz[0]), float(y_lorenz[0])],
              "ccdf": ccdf_checks, "hardcoded_statistical_values": False,
              "q2_q3": "NOT_RUN; original ZIP figure sections not changed",
              "files": {name: hashlib.sha256((args.out / name).read_bytes()).hexdigest()
                        for name in ["fig1_data_patterns.pdf", "fig1_data_patterns.png"]}}
    (args.out / "q1_figure.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    if args.paper_reference:
        paper_reference_figures(nodes, jobs, stats, pools, args.out)
    print("Generated Q1 fig1_data_patterns.pdf and .png from the raw CSVs and matching Q1 results")


if __name__ == "__main__":
    main()
