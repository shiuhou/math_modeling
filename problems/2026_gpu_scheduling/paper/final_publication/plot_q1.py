#!/usr/bin/env python3
"""Reuse audited Q1 plot data and formulas; render axis ticks in full-size type."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[4]
PROBLEM=ROOT/'problems/2026_gpu_scheduling'
sys.path.insert(0,str(PROBLEM/'experiments'))
import generate_figures as q1

def save(fig,out,name):
    if name=='fig1_data_patterns':
        ax=fig.axes[1]
        ax.set_xticks([.01,1,100,10000],labels=['0.01','1','100','10000'])
        ax.set_yticks([1,.01,.0001],labels=['1','0.01','0.0001'])
        ax.minorticks_off()
    fig.savefig(out/f'{name}.pdf')
    q1.plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);a=p.parse_args()
    nodes,jobs,hashes=q1.load_data(a.data)
    stats=json.loads((ROOT/'results/20261014-b-q1-intake-4a8f8f2b/q1_results.json').read_text())
    assert hashes==stats['input_sha256']
    q1.plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11.2,'axes.titlesize':11.2,'axes.labelsize':11.2,'xtick.labelsize':11.2,'ytick.labelsize':11.2,'legend.fontsize':11.2,'pdf.fonttype':42})
    q1.save_figure=save
    q1.main_figures(nodes,jobs,stats,Path(__file__).with_name('figures'))
