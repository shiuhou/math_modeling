#!/usr/bin/env python3
"""Generate publication and supplementary Q1 figures from audited data.

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
import numpy as np
import pandas as pd
from gpu_scheduling.q1 import ccdf, gini, load_data, lorenz, top_share, demand_timeline, interval_demand


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


PALETTE = ['#c0392b', '#1b4f72', '#27ae60', '#8e44ad', '#e67e22', '#2e86c1']
SHORT = {'A10': 'A10', 'A100-SXM4-80GB': 'A100', 'A800-SXM4-80GB': 'A800',
         'GPU-series-1': 'GPU-s1', 'GPU-series-2': 'GPU-s2', 'ALL': 'All jobs'}


def save_figure(fig, out, name):
    # Fixed page-width canvas: no tight bounding-box rescaling of 11pt labels.
    fig.savefig(out/f'{name}.pdf')
    fig.savefig(out/f'{name}.png', dpi=200)
    plt.close(fig)


def draw_lorenz(ax, values, label, color, style='-'):
    x,y=lorenz(values)
    sample=np.unique(np.r_[0,np.linspace(0,len(x)-1,1000).astype(int)])
    ax.plot(x[sample]*100,y[sample]*100,label=label,color=color,linestyle=style)


def draw_ccdf(ax, values, label, color, style='-'):
    durations,probability=ccdf(values)
    positive=probability>0
    if positive.any():
        ax.step(np.r_[durations[positive],durations[-1]]/3600,
                np.r_[probability[positive],probability[positive][-1]],where='post',
                label=label,color=color,linestyle=style)
    ax.set(xscale='log',yscale='log')


def main_figures(nodes,jobs,stats,out):
    fig,axes=plt.subplots(1,2,figsize=(6.70,2.35),layout='constrained')
    ax=axes[0]
    draw_lorenz(ax,jobs.gpu_seconds,'GPU work',PALETTE[0])
    ax.plot([0,100],[0,100],color='#777777',linestyle='--',linewidth=.9)
    for fraction in [.01,.05]:
        k,share=top_share(jobs.gpu_seconds,fraction)
        ax.scatter(100*(1-k/len(jobs)),100*(1-share),color=PALETTE[0],s=18)
    ax.text(.04,.95,f'Gini {gini(jobs.gpu_seconds):.4f}\nTop 1%: {top_share(jobs.gpu_seconds,.01)[1]*100:.2f}%\nTop 5%: {top_share(jobs.gpu_seconds,.05)[1]*100:.2f}%',
            transform=ax.transAxes,va='top',fontsize=11.2)
    ax.set(xlabel='Jobs, cumulative (%)',ylabel='GPU work (%)',xlim=(0,100),ylim=(0,100),title='(a) Work concentration')
    ax=axes[1]
    for model,color,style in [('ALL','#333333','-'),('A10',PALETTE[0],'--'),('A100-SXM4-80GB',PALETTE[1],':')]:
        sub=jobs if model=='ALL' else jobs[jobs.gpu_model==model]
        draw_ccdf(ax,sub.duration,SHORT[model],color,style)
    ax.set(xlabel='Duration (hours)',ylabel='P(duration > d)',title='(b) Duration tails')
    ax.legend(loc='lower left',frameon=False)
    for ax in axes: ax.grid(alpha=.2)
    save_figure(fig,out,'fig1_data_patterns')

    fig,ax=plt.subplots(figsize=(6.70,2.0),layout='constrained')
    records=[]
    for model,color in [('A10',PALETTE[0]),('A100-SXM4-80GB',PALETTE[1])]:
        sub=jobs[jobs.gpu_model==model]
        bins,areas=interval_demand(sub.submit_time,sub.duration,sub.total_gpu,stats['horizon_seconds'])
        means=areas/np.diff(bins)
        capacity=int(nodes.loc[nodes.gpu_model==model,'gpu_capacity_num'].sum())
        ax.stairs(means,bins/86400,color=color,label=SHORT[model]+' demand')
        ax.axhline(capacity,color=color,linestyle='--',label=SHORT[model]+' capacity')
        records.extend({'gpu_model':model,'start_seconds':int(a),'end_seconds':int(b),
                        'gpu_seconds':int(area),'mean_gpus':float(mean),'capacity':capacity}
                       for a,b,area,mean in zip(bins[:-1],bins[1:],areas,means))
    ax.set(xlabel='Trace-relative day',ylabel='GPUs',xlim=(0,stats['horizon_seconds']/86400))
    # Upper bound comes from data (headroom for a two-column legend).
    ax.set_ylim(0,max(max(r['mean_gpus'],r['capacity']) for r in records)*1.65)
    ax.legend(ncol=2,loc='upper left',frameon=False,columnspacing=1.5)
    ax.grid(alpha=.2)
    save_figure(fig,out,'fig1_demand')
    pd.DataFrame(records).to_csv(out/'q1_daily_demand.csv',index=False,float_format='%.12g')


def supplementary_figures(nodes,jobs,stats,results,out):
    models=pd.read_csv(results/'pool_summary.csv').gpu_model.tolist()
    fig,axes=plt.subplots(1,2,figsize=(10,4.8),layout='constrained')
    for i,model in enumerate(models):
        sub=jobs[jobs.gpu_model==model];style=['-','--',':','-.','-','--'][i%6]
        draw_lorenz(axes[0],sub.gpu_seconds,SHORT.get(model,model),PALETTE[i%6],style)
        draw_ccdf(axes[1],sub.duration,SHORT.get(model,model),PALETTE[i%6],style)
    axes[0].plot([0,100],[0,100],color='#999999',linestyle=':')
    axes[0].set(xlabel='Jobs, cumulative (%)',ylabel='GPU work, cumulative (%)',title='S1a. Lorenz curves by GPU model')
    axes[1].set(xlabel='Duration (hours)',ylabel='P(duration > d)',title='S1b. Strict duration CCDF')
    for ax in axes:ax.legend(frameon=False);ax.grid(alpha=.2)
    save_figure(fig,out,'supplement_model_distributions')

    pools=pd.read_csv(results/'pool_summary.csv')
    fig,ax=plt.subplots(figsize=(8,4),layout='constrained');x=np.arange(len(pools))
    for offset,key,label,color in [(-.25,'capacity_share','Physical GPUs',PALETTE[1]),(0,'job_share','Submitted jobs',PALETTE[2]),(.25,'work_share','Lifetime GPU work',PALETTE[0])]:
        ax.bar(x+offset,pools[key]*100,width=.25,label=label,color=color)
    ax.set_xticks(x,[SHORT.get(m,m) for m in pools.gpu_model]);ax.set(ylabel='Share (%)',title='S2. Supply and submitted demand shares')
    ax.legend(frameon=False);ax.grid(axis='y',alpha=.2);save_figure(fig,out,'supplement_supply_shares')

    daily=pd.read_csv(results/'daily_arrivals.csv');frame=daily[daily.gpu_model=='ALL']
    fig,axes=plt.subplots(2,1,figsize=(8,5.5),layout='constrained',sharex=True)
    axes[0].plot(frame.trace_day,frame.jobs,color=PALETTE[1],label='All submissions')
    axes[0].plot(frame.trace_day,frame.jobs_excluding_t0,color=PALETTE[0],linestyle='--',label='Excluding trace-origin batch')
    axes[0].set(ylabel='Jobs submitted',title='S3. Daily submissions and lifetime work');axes[0].legend(frameon=False)
    axes[1].plot(frame.trace_day,frame.submitted_full_lifetime_gpu_hours/1e6,color=PALETTE[1],label='All submitted work')
    axes[1].plot(frame.trace_day,(frame.submitted_full_lifetime_gpu_hours-frame.t0_gpu_hours)/1e6,color=PALETTE[0],linestyle='--',label='Excluding trace-origin batch')
    axes[1].set(xlabel='Trace-relative day',ylabel='Million GPU-hours');axes[1].legend(frameon=False)
    for ax in axes:ax.grid(alpha=.2)
    save_figure(fig,out,'supplement_daily_arrivals_work')

    phases=pd.read_csv(results/'relative_24h_phase.csv');fig,ax=plt.subplots(figsize=(8,3.8),layout='constrained')
    for model,color,style in [('ALL','#333333','-'),('A10',PALETTE[0],'--'),('A100-SXM4-80GB',PALETTE[1],':')]:
        frame=phases[phases.gpu_model==model].sort_values('relative_phase_hour')
        ax.plot(frame.relative_phase_hour,frame.jobs_per_exposed_hour,color=color,linestyle=style,label=SHORT[model])
    ax.set(xlabel='Relative trace phase (hour modulo 24; no timezone)',ylabel='Jobs per exposed hour',title='S4. Exposure-corrected phase profile (t > 0)')
    ax.set_xticks(range(0,24,2));ax.legend(frameon=False);ax.grid(alpha=.2);save_figure(fig,out,'supplement_relative_phase')

    shape=pd.read_csv(results/'resource_shape.csv');shape=shape[shape.gpu_model=='GPU-series-1'].sort_values('node_cpu_per_gpu')
    fig,ax=plt.subplots(figsize=(8,4.2),layout='constrained');x=np.arange(len(shape))
    ax.bar(x-.18,shape.fraction_jobs_above_ratio*100,width=.36,label='Jobs above ratio',color=PALETTE[1])
    ax.bar(x+.18,shape.work_share_above_ratio*100,width=.36,label='Work from those jobs',color=PALETTE[0])
    ax.set_xticks(x,[f'{r.node_cpu_per_gpu:g} vCPU/GPU\n{r.gpus_per_node:g} GPU, {r.vcpus_per_node:g} vCPU\n{r.nodes:g} nodes' for r in shape.itertuples()])
    ax.set(ylabel='Share within GPU-series-1 (%)',title='S5. Jobs exceeding each node configuration ratio')
    ax.legend(frameon=False);ax.grid(axis='y',alpha=.2);save_figure(fig,out,'supplement_resource_shape')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=PROBLEM/'data/raw')
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True,help='New figure directory')
    parser.add_argument('--figures',choices=['main','supplementary','all'],default='main')
    parser.add_argument('--paper-reference',action='store_true',help='Also render archived Q2/Q3 figures, marked NOT_RUN')
    args=parser.parse_args()
    if args.out.exists():parser.error('Output exists; choose a new directory')
    nodes,jobs,hashes=load_data(args.data)
    stats=json.loads((args.results/'q1_results.json').read_text(encoding='utf-8'))
    if hashes!=stats['input_sha256']:parser.error('Q1 results and raw input byte hashes differ')
    pools=pd.read_csv(args.results/'pool_summary.csv')
    if set(pools.gpu_model)!=set(jobs.gpu_model):parser.error('Pool summary does not match raw GPU models')
    args.out.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11.2,'axes.titlesize':11.2,'axes.labelsize':11.2,
                         'xtick.labelsize':11.2,'ytick.labelsize':11.2,'legend.fontsize':11.2,
                         'axes.edgecolor':'#333333','axes.linewidth':.8,'pdf.fonttype':42})
    if args.figures in ['main','all']:main_figures(nodes,jobs,stats,args.out)
    if args.figures in ['supplementary','all']:supplementary_figures(nodes,jobs,stats,args.results,args.out)
    record={'scope':'Q1 '+args.figures,'input_sha256':hashes,
            'results_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.results.iterdir()) if p.suffix in ['.json','.csv']},
            'main_width_inches':6.70,'main_label_points':11.2,'lorenz_origin':[0,0],
            'ccdf':'strict P(duration > d), ties grouped; terminal zero omitted on log axes',
            'top_k_rule':stats['top_k_rule'],'daily_demand':'Exact event integral within each bin; final partial day retained',
            'q2_q3':'NOT_RUN; optional archived figures only',
            'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.out.iterdir()) if p.is_file()}}
    (args.out/'q1_figure.json').write_text(json.dumps(record,indent=2)+'\n')
    if args.paper_reference:paper_reference_figures(nodes,jobs,stats,pools,args.out)
    print(f'Generated Q1 {args.figures} figures from matching raw CSVs and results')


if __name__=='__main__':main()
