#!/usr/bin/env python3
"""Redraw saved donor sensitivity at publication size; no new experiment."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[4]
def main():
    one=json.loads((ROOT/'results/20261015-b-q3-fixed-split-c9e8f1a2/metrics.json').read_text())
    two=json.loads((ROOT/'results/20261015-b-q3-s2-fixed-split-v1/sensitivity_metrics.json').read_text())
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11.5,'axes.labelsize':11.5,'axes.titlesize':11.5,'xtick.labelsize':11.5,'ytick.labelsize':11.5,'legend.fontsize':11.5,'pdf.fonttype':42})
    fig,axes=plt.subplots(1,2,figsize=(6.7,2.65),layout='constrained')
    saved={}
    for policy,label,color in [('FCFS','FCFS','#1565c0'),('SJF-HOL','SPT-HOL','#c62828')]:
        a=[];n=[]
        for donor in [30,60,90]:
            if donor==60:
                x=one[policy]['M1']['cohorts'];b=one[policy]['M0']['cohorts']
                a.append(b['original_A10']['mean_wait_hours']-x['original_A10']['mean_wait_hours'])
                n.append(x['native_A100']['mean_wait_hours']-b['native_A100']['mean_wait_hours'])
            else:
                x=two['S3' if donor==30 else 'S4'][policy]['paired_M0']
                a.append(-x['A10']['mean_delta_wait_hours']);n.append(x['native_A100']['mean_delta_wait_hours'])
        axes[0].plot([30,60,90],a,'o-',color=color,label=label)
        axes[1].plot([30,60,90],n,'o-',color=color,label=label)
        saved[label]={'donors':[30,60,90],'a10_mean_wait_reduction_h':a,'native_a100_mean_wait_increase_h':n}
    for ax in axes:
        ax.set_xlabel('Dedicated A100 nodes');ax.set_xticks([30,60,90]);ax.axhline(0,color='gray',lw=.7);ax.grid(alpha=.2)
    axes[0].set_ylabel('A10 wait reduction (h)');axes[1].set_ylabel('Native A100 wait\nincrease (h)')
    axes[0].legend(loc='upper left',frameon=False)
    fig.savefig(Path(__file__).with_name('figures')/'q3_donor_capacity_wait_tradeoff.pdf')
    (Path(__file__).with_name('generated')/'sensitivity_plot_values.json').write_text(json.dumps(saved,indent=2)+'\n')
if __name__=='__main__':main()
