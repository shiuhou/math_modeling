#!/usr/bin/env python3
"""Publication-only generation from saved, keyed formal evidence; no simulation."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUNTIME = 'results/20261019-b-v2-integration-candidate/v2_runtime_equivalence.json'
R2 = 'results/20261019-paper-content-r2/r2_metrics.json'
PAIRS = 'results/20261020-final-publication/saved_timing_checks.json'
FCFS = 'results/20261018-b-q3-v2-r1-6f2c8a10/main_table.csv'

def tex(s):
    return str(s).replace('%',r'\%').replace('_',r'\_').replace('&',r'\&')

def table(caption,label,columns,header,rows,note=''):
    return '\n'.join([r'\begin{table}[H]\centering',r'\caption{'+caption+'}',r'\label{'+label+'}',r'\begin{tabular}{'+columns+'}',r'\toprule',header+r'\\',r'\midrule',*[r' & '.join(row)+r'\\' for row in rows],r'\bottomrule',r'\end{tabular}',r'\smallskip\par '+note if note else '',r'\end{table}'])+'\n'

def generate(root,out):
    out.mkdir(parents=True,exist_ok=True)
    runtime={r['case']:r for r in json.loads((root/RUNTIME).read_text())['cases']}
    r2=json.loads((root/R2).read_text())
    pairs={r['case']:r for r in json.loads((root/PAIRS).read_text())['records']}
    records=[]
    options={'C0':'No substitution','C1':'Hash-10%','C2':'Hash-10%','C3':'Shape-filtered','C4':'Shape-filtered'}
    for case in options:
        row=runtime[case];a=row['metrics']['cohorts']['original_A10'];all_=row['metrics']['cohorts']['ALL']
        assert row['policy']=='SJF-HOL' and row['placement_policy']=={'GPU-series-1':'ratio','other_pools':'ff-id'}
        values={'a10_wait':a['mean_wait_hours'],'a10_jct':a['mean_jct_hours'],'all_jct':all_['mean_jct_hours'],'done':all_['completed_at_horizon'],'native_harm':pairs[case]['native_a100_wait_increase_count'],'a10_harm':pairs[case]['a10_later_finish_count']}
        fields={'a10_wait':'metrics.cohorts.original_A10.mean_wait_hours','a10_jct':'metrics.cohorts.original_A10.mean_jct_hours','all_jct':'metrics.cohorts.ALL.mean_jct_hours','done':'metrics.cohorts.ALL.completed_at_horizon','native_harm':'native_a100_wait_increase_count','a10_harm':'a10_later_finish_count'}
        records.append({'case':case,'policy':'SPT-HOL','historical_policy_alias':row['policy'],'placement':row['placement_policy'],'routing':{'C0':'M0','C1':'R0','C2':'R0','C3':'R-shape','C4':'R-shape'}[case],'display':options[case],'sigma':None if case=='C0' else row['config']['sigma'],'cohort':{'a10':'original_A10','all':'ALL','native':'native_A100'},'fields':fields,'metric_source':RUNTIME,'harm_source':PAIRS,'baseline':'No-substitution (C0)','values':values})
    perf=[];harm=[]
    for r in records:
        v=r['values'];prefix=[tex(r['display']),r'---' if r['sigma'] is None else str(r['sigma'])]
        perf.append(prefix+[f'{v[k]:.3f}' for k in ['a10_wait','a10_jct','all_jct']]+[f"{v['done']:,}"])
        harm.append(prefix+[f"{v['native_harm']:,}",f"{v['a10_harm']:,}"])
    s=table('Fixed-split results: (a) performance. Waiting and JCT use complete drain; completions use the 90-day horizon.','tab:q3main','lrrrrr',r'Scenario & $\sigma$ & \shortstack{A10 mean\\wait (h)} & \shortstack{A10 mean\\JCT (h)} & \shortstack{All mean\\JCT (h)} & \shortstack{90-day\\completions}',perf)
    # Keep both parts under Table 5, with readable full-size columns.
    s+=r'\addtocounter{table}{-1}'+'\n'
    s+=table('Fixed-split results: (b) harm relative to the No-substitution baseline. A10 harm means a later completion; native A100 harm means increased waiting.','tab:q3harm','lrrr',r'Scenario & $\sigma$ & \shortstack{Native A100\\increased-wait jobs} & \shortstack{A10 later-\\completion jobs}',harm,'Both parts use SPT-HOL, GS1 ratio placement, and FF-id in the other pools. Substitution scenarios dedicate 60 A100 nodes to foreign jobs. No substitution keeps the full native pools and has no foreign partition.')
    (out/'table5.tex').write_text(s)
    labels={'A10':'A10','A100-SXM4-80GB':'A100','GPU-series-1':'GS1','GPU-series-2':'GS2','H800':'H800','A800-SXM4-80GB':'A800'}
    rows=[]
    for pool,label in labels.items():
        r=r2['q2_c0_six_pool'][pool]
        rows.append([label,f"{r['jobs']:,}",f"{r['gpus']:,}",f"{r['mean_wait_h']:.3f}",f"{r['median_wait_h']:.3f}/{r['p99_wait_h']:.3f}",f"{r['gpu_alloc']*100:.3f}\\%/{r['cpu_alloc']*100:.3f}\\%",f"{r['done90']:,}"])
    (out/'table2.tex').write_text(table('Six-pool SPT-HOL results. GS1 uses ratio; other pools use FF-id. Waiting uses complete drain; allocation and completion use $H=7{,}776{,}000$ s.','tab:r2pools','lrrrrrr',r'Pool & Jobs & GPUs & \shortstack{Mean\\wait (h)} & \shortstack{Median/P99\\wait (h)} & \shortstack{GPU/CPU\\allocation} & \shortstack{90-day\\done}',rows,'A100 and A800 denote the SXM4-80GB models; GS1 and GS2 denote GPU-series-1 and GPU-series-2. Allocation integrates $[0,H)$; a completion at $H$ is included.'))
    q2=r2['q2_a10_three_policy']; rows=[]
    for policy,key in [('FCFS','FCFS_B1'),('SPT-HOL','SPT-HOL_C0'),('SPT-FILL','SPT-FILL_full-A1')]:
        r=q2[key];rows.append([policy]+[f'{r[k]:.3f}' for k in ['mean_wait_h','p99_wait_h','max_wait_h','gpu_work_weighted_mean_wait_h']])
    (out/'table3.tex').write_text(table('Complete A10 waiting comparison using the same 111,284 jobs and fixed native GPU-work weights.','tab:r2a10','lrrrr',r'Policy & Mean (h) & P99 (h) & Max (h) & \shortstack{GPU-work-weighted\\mean (h)}',rows))
    rows=[]
    for key,label in [('W=1',r'$W=1$'),('W=2-8',r'$W=2$--8'),('W>=9',r'$W\ge9$')]:
        r=r2['q2_worker_strata'][key];dagger='' if key=='W=1' else r'$^\dagger$'
        rows.append([label,f"{r['jobs']:,}",f"{r['hol_mean_wait_h']:.3f}",f"{r['fill_mean_wait_h']:.3f}",f"{r['hol_p99_wait_h']:.3f}"+dagger,f"{r['fill_p99_wait_h']:.3f}"+dagger,f"${r['paired_diff_h']:+.3f}$",r'\shortstack{'+r' / '.join([f"{r['improved_hol']:,}",f"{r['worsened_hol']:,}"])+r'\\ / '+f"{r['unchanged']:,}"+'}'])
    (out/'table4.tex').write_text(table('HOL/FILL worker strata: waiting in hours; paired difference is HOL minus FILL.','tab:r2strata','lrrrrrrr',r'Stratum & Jobs & \shortstack{HOL\\mean} & \shortstack{FILL\\mean} & \shortstack{HOL\\P99} & \shortstack{FILL\\P99} & \shortstack{Paired\\mean} & \shortstack{Improve / worsen\\/ same (jobs)}',rows,r'$^\dagger$ Small strata; P99 is unstable. The groups use the same complete A10 population.'))
    fcfs=list(csv.DictReader((root/FCFS).open()))
    wins={}
    for policy in ['FCFS','SPT-HOL']:
        vals={}
        for sigma in [1,2]:
            if policy=='SPT-HOL':
                h=records[sigma]['values']['a10_jct'];sh=records[sigma+2]['values']['a10_jct']
            else:
                def select(option):
                    match=[r for r in fcfs if r['policy']=='FCFS' and r['option']==option and float(r['sigma'])==sigma and r['cohort']=='A10']
                    assert len(match)==1;return float(match[0]['mean_jct_hours'])
                h=select('R0');sh=select('R-shape')
            vals[str(sigma)]={'Hash-10%':h,'Shape-filtered':sh,'winner':'Hash-10%' if h<sh else 'Shape-filtered'}
        vals['two_point_max']={opt:max(vals['1'][opt],vals['2'][opt]) for opt in ['Hash-10%','Shape-filtered']}
        assert vals['1']['winner']=='Hash-10%' and vals['2']['winner']=='Shape-filtered'
        assert vals['two_point_max']['Shape-filtered']<vals['two_point_max']['Hash-10%']
        wins[policy]=vals
    ratio=q2['FCFS_B1']['mean_wait_h']/q2['SPT-HOL_C0']['mean_wait_h']
    claim=r'For both FCFS and SPT-HOL, Hash-10\% achieves lower mean A10 JCT at $\sigma=1$, whereas Shape-filtered achieves lower mean A10 JCT at $\sigma=2$. Shape-filtered also has the smaller worst-case value across these two evaluated scenarios.'
    macros=r'\newcommand{\WinnerClaim}{'+claim+'}\n'
    macros=macros.replace('}\\n','}\n')
    macros+=r'\newcommand{\FCFSratio}{'+f'{ratio:.2f}'+'}\n'
    macros+=r'\newcommand{\BaselineWait}{'+f"{records[0]['values']['a10_wait']:.3f}"+'}\n'
    macros+=r'\newcommand{\HashWait}{'+f"{records[1]['values']['a10_wait']:.3f}"+'}\n'
    (out/'claims.tex').write_text(macros)
    sources={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [RUNTIME,R2,PAIRS,FCFS]}
    (out/'numerical_source_map.json').write_text(json.dumps({'records':records,'winners':wins,'fcfs_hol_mean_ratio':ratio,'sources_sha256':sources},indent=2)+'\n')
    return records

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--out',type=Path,default=Path(__file__).with_name('generated'))
    a=p.parse_args();generate(a.root,a.out)
