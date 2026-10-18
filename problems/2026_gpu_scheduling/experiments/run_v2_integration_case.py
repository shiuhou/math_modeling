#!/usr/bin/env python3
"""Run one frozen V2 integration case in a clean child process.

The runner is deliberately bounded to the seven cases named in the V2
integration task.  It uses the integrated q3/simulator modules and writes
large CSV ledgers only under the ignored output root.
"""
from __future__ import annotations
import argparse, hashlib, json, math, resource, subprocess, time
from pathlib import Path
import numpy as np
import pandas as pd
from gpu_scheduling.data import read_data, native
from gpu_scheduling.q3 import Config, SOURCE, TARGET, FOREIGN, describe, fits, route, selected
from gpu_scheduling.q3_v2 import route_shape, derive_shape_limit, shape_allowed
from gpu_scheduling.simulator import simulate_pool
from gpu_scheduling.q3_validation import verify_schedule, verify_metrics, require
from gpu_scheduling.validation import validate

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
HORIZON = 7_776_000
TARGET_POOL = "GPU-series-1"
GS1_JOBS = Path("/home/shiuhou/mm/math_modeling-b-gang-placement/results/20261018-b-gs1-placement-v2-r1/spt-hol-ratio-seedid-job-times.csv.gz")
GS1_LEDGER = Path("/home/shiuhou/mm/math_modeling-b-gang-placement/results/20261018-b-gs1-placement-v2-r1/spt-hol-ratio-seedid-placements.csv.gz")
V1_ROOT = Path("/home/shiuhou/mm/math_modeling-b-q3/outputs/b-q3-fixed-split-v1-final")
R0_SIGMA2_ROOT = Path("/home/shiuhou/mm/math_modeling-b-q3-substitution-v2/outputs/q3-v2-r0-sigma2/S5_SJF-HOL")
RSHAPE_ROOT = Path("/home/shiuhou/mm/math_modeling-b-q3-substitution-v2/outputs/q3-v2-shape-a17c4e9d")

CASES = {
    "B1": {"route": "M0", "policy": "FCFS", "placement": "ff-id", "base": "M0"},
    "B2": {"route": "M0", "policy": "SJF-HOL", "placement": "ff-id", "base": "M0"},
    "C0": {"route": "M0", "policy": "SJF-HOL", "placement": "ratio-gs1", "base": "M0"},
    "C1": {"route": "R0", "policy": "SJF-HOL", "placement": "ratio-gs1", "sigma": 1, "base": "R0-sigma1"},
    "C2": {"route": "R0", "policy": "SJF-HOL", "placement": "ratio-gs1", "sigma": 2, "base": "R0-sigma2"},
    "C3": {"route": "R-shape", "policy": "SJF-HOL", "placement": "ratio-gs1", "sigma": 1, "base": "Rshape-sigma1"},
    "C4": {"route": "R-shape", "policy": "SJF-HOL", "placement": "ratio-gs1", "sigma": 2, "base": "Rshape-sigma2"},
}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def save_frame(out, frame, ledger):
    frame.to_csv(out/'jobs.csv.gz', index=False, compression='gzip')
    ledger.to_csv(out/'placements.csv.gz', index=False, compression='gzip')

def load_reference(case):
    base = CASES[case]['base']
    if base == 'M0':
        root=V1_ROOT; j=root/'SJF-HOL_M0_jobs.csv.gz'; p=root/'SJF-HOL_M0_placements.csv.gz'
    elif base == 'R0-sigma1':
        root=V1_ROOT; j=root/'SJF-HOL_M1_jobs.csv.gz'; p=root/'SJF-HOL_M1_placements.csv.gz'
    elif base == 'R0-sigma2':
        j=R0_SIGMA2_ROOT/'jobs.csv.gz'; p=R0_SIGMA2_ROOT/'placements.csv.gz'
    else:
        root=RSHAPE_ROOT; j=root/f'Rshape_sigma{CASES[case]["sigma"]}_SJF-HOL/jobs.csv.gz'; p=root/f'Rshape_sigma{CASES[case]["sigma"]}_SJF-HOL/placements.csv.gz'
    return pd.read_csv(j), pd.read_csv(p)

def gs1_reference():
    return pd.read_csv(GS1_JOBS), pd.read_csv(GS1_LEDGER)

def compare_subset(actual, ledger, ref, ref_ledger, ids, label):
    ids=set(int(x) for x in ids)
    a=actual[actual.job_name.isin(ids)].copy().sort_values('job_name').reset_index(drop=True)
    b=ref[ref.job_name.isin(ids)].copy().sort_values('job_name').reset_index(drop=True)
    if not a.job_name.equals(b.job_name): return {'status':'FAIL','label':label,'kind':'timing','first_diff':'job_id_set'}
    fields=['submit_time','original_duration','duration','worker_num','gpu_request','cpu_units','start','finish','original_gpu_model','gpu_model','partition','route_reason']
    # GS1 files contain only native fields; compare common timing/resource fields there.
    fields=[f for f in fields if f in a and f in b]
    for f in fields:
        av=a[f].to_numpy(); bv=b[f].to_numpy()
        if not np.array_equal(av,bv):
            i=int(np.flatnonzero(av!=bv)[0]); return {'status':'FAIL','label':label,'kind':'timing','field':f,'job_name':int(a.iloc[i].job_name),'actual':native(av[i]),'expected':native(bv[i])}
    la=ledger[ledger.job_name.isin(ids)].copy().sort_values(['job_name','node_name','workers']).reset_index(drop=True)
    lb=ref_ledger[ref_ledger.job_name.isin(ids)].copy().sort_values(['job_name','node_name','workers']).reset_index(drop=True)
    if not la.equals(lb):
        n=min(len(la),len(lb))
        for i in range(n):
            if tuple(la.iloc[i]) != tuple(lb.iloc[i]): return {'status':'FAIL','label':label,'kind':'placement','row':i,'actual':native(la.iloc[i].to_dict()),'expected':native(lb.iloc[i].to_dict())}
        return {'status':'FAIL','label':label,'kind':'placement','row':n,'actual_rows':len(la),'expected_rows':len(lb)}
    return {'status':'PASS','label':label,'jobs':len(a),'placements':len(la)}

def independent_route_audit(nodes, original, frame, config, shape=False):
    raw=original.set_index('job_name').sort_index(); got=frame.set_index('job_name').sort_index()
    require(raw.index.equals(got.index), 'raw job ID set')
    donor=nodes[nodes.gpu_model==TARGET].sort_values('node_name').head(config.donor_nodes) if config.compatibility else nodes.iloc[:0]
    eligible={}
    for q,c,w in raw.loc[raw.gpu_model==SOURCE,['gpu_request','cpu_units','worker_num']].drop_duplicates().itertuples(index=False,name=None):
        eligible[int(q),int(c),int(w)] = fits(donor,int(q),int(c),int(w)) if config.compatibility else False
    limit=derive_shape_limit(nodes,config.donor_nodes) if shape else None
    for jid,r in got.iterrows():
        src=raw.loc[jid]
        if src.gpu_model != SOURCE: reason='native'
        elif not config.compatibility: reason='disabled'
        elif not eligible[int(src.gpu_request),int(src.cpu_units),int(src.worker_num)]: reason='structurally_infeasible'
        elif not selected(jid,config): reason='hash_unselected'
        elif shape and not shape_allowed(src,limit): reason='shape_rejected'
        else: reason='routed'
        require(r.route_reason==reason,f'route reason {jid}')
        routed=reason=='routed'; expected_model=TARGET if routed else src.gpu_model
        require(r.gpu_model==expected_model,f'actual model {jid}')
        require(r.partition==(FOREIGN if routed else src.gpu_model),f'partition {jid}')
        require(int(r.duration)==int(src.duration)*(config.sigma if routed else 1),f'duration {jid}')
    return {'status':'PASS','shape_limit_cpu_per_gpu':limit}

def physical_replay(nodes, original, frame, ledger):
    ordered_nodes=nodes.sort_values('node_name').reset_index(drop=True)
    saved=frame.sort_values('job_name').reset_index(drop=True)
    ni={int(v):i for i,v in enumerate(ordered_nodes.node_name)}
    ji={int(v):i for i,v in enumerate(saved.job_name)}
    plans=[[] for _ in range(len(saved))]
    for j,n,w in ledger.itertuples(index=False,name=None): plans[ji[int(j)]].append((ni[int(n)],int(w)))
    validate(ordered_nodes,saved,saved.start.to_numpy(dtype='int64'),saved.finish.to_numpy(dtype='int64'),plans)
    return {'status':'PASS','jobs':len(saved),'placements':len(ledger)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--case',choices=CASES,required=True); ap.add_argument('--out',type=Path,required=True); args=ap.parse_args()
    spec=CASES[args.case]; started=time.perf_counter(); args.out.mkdir(parents=True,exist_ok=False)
    nodes,jobs,hashes=read_data(ROOT/'data/raw')
    compat=spec['route']!='M0'; sigma=spec.get('sigma',1)
    config=Config(60,1,10,compat,sigma,HORIZON,'q3-fixed-split-v1')
    if spec['route']=='R-shape': pools,routed=route_shape(nodes,jobs,config); shape=True
    else: pools,routed=route(nodes,jobs,config); shape=False
    frames=[]; rows=[]
    placement_map={TARGET_POOL:'ratio'} if spec['placement']=='ratio-gs1' else {}
    for key,sub in routed.groupby('partition',sort=True):
        pool=pools[key].sort_values('node_name').reset_index(drop=True)
        placement=placement_map.get(key,'ff-id')
        result=simulate_pool(pool,sub,spec['policy'],theta_seconds=4_860_000,reservation_k=200,event_mode='shared-timer',diagnostics=True,placement=placement)
        f=result['jobs'].copy(); f['start']=result['starts']; f['finish']=result['ends']; frames.append(f)
        rows.extend((int(jid),int(pool.node_name.iloc[i]),int(w)) for jid,plan in zip(f.job_name,result['plans']) for i,w in plan)
    frame=pd.concat(frames,ignore_index=True).sort_values('job_name').reset_index(drop=True)
    ledger=pd.DataFrame(rows,columns=['job_name','node_name','workers']).sort_values(['job_name','node_name']).reset_index(drop=True)
    save_frame(args.out,frame,ledger)
    if spec['route']=='M0' or spec['route']=='R0':
        physical=verify_schedule(nodes,jobs,frame,ledger,config)
        route_audit=independent_route_audit(nodes,jobs,frame,config,False)
    else:
        route_audit=independent_route_audit(nodes,jobs,frame,config,True)
        physical=physical_replay(nodes,jobs,frame,ledger)
    report=describe(nodes,frame,config); metric_check=verify_metrics(nodes,frame,config,report)
    ref,refled=load_reference(args.case)
    gs,gsled=gs1_reference()
    base_ids=set(frame.job_name)
    gs_ids=set(jobs[jobs.gpu_model==TARGET_POOL].job_name)
    non_gs=base_ids-gs_ids
    comparisons=[compare_subset(frame,ledger,ref,refled,non_gs,'non-GS1-vs-frozen-reference'), compare_subset(frame,ledger,gs,gsled,gs_ids,'GS1-vs-ratio-reference')]
    status='PASS' if all(x['status']=='PASS' for x in comparisons) and physical['status']=='PASS' and route_audit['status']=='PASS' and metric_check['status']=='PASS' else 'FAIL'
    meta={'case':args.case,'status':status,'current_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'config':config.dictionary(),'policy':spec['policy'],'placement_policy':{'GPU-series-1':'ratio' if spec['placement']=='ratio-gs1' else 'ff-id','other_pools':'ff-id'},'event_mode':'shared-timer','theta_seconds':4860000,'horizon_seconds':HORIZON,'raw_hashes':hashes,'rows':len(frame),'placements':len(ledger),'jobs_sha256':sha(args.out/'jobs.csv.gz'),'placements_sha256':sha(args.out/'placements.csv.gz'),'route_audit':route_audit,'physical_validation':physical,'metric_validation':metric_check,'metrics':report,'comparisons':comparisons,'wall_seconds':time.perf_counter()-started,'max_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,'timeout_seconds':900,'address_space_limit_mib':4096}
    (args.out/'run_metadata.json').write_text(json.dumps(native(meta),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'case':args.case,'status':status,'wall_seconds':meta['wall_seconds'],'max_rss_mib':meta['max_rss_mib']}))
    raise SystemExit(0 if status=='PASS' else 1)
if __name__=='__main__': main()
