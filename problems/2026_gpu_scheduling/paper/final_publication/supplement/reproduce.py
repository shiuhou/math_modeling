#!/usr/bin/env python3
"""Portable packaging adapter to unchanged research functions; explicit input/output."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PROBLEM=ROOT/'problems/2026_gpu_scheduling'
sys.path.insert(0,str(PROBLEM/'src'))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',required=True,choices=['B1','B2','C0','C1','C2','C3','C4','full-H1','full-A1','full-C1'])
    p.add_argument('--data',type=Path,required=True,help='Official CSV directory (or synthetic smoke fixture)')
    p.add_argument('--output',type=Path,required=True,help='New directory')
    a=p.parse_args()
    if a.output.exists():p.error('Output directory already exists')
    import pandas as pd
    from gpu_scheduling.data import read_data,native
    from gpu_scheduling.q3 import Config,route,describe
    from gpu_scheduling.q3_v2 import route_shape
    from gpu_scheduling.simulator import simulate_pool
    from gpu_scheduling.evaluation import metrics
    specs=json.loads((ROOT/'frozen_cases.json').read_text())
    spec=specs[a.case];nodes,jobs,hashes=read_data(a.data)
    cfg=Config(**spec['config'])
    if a.case.startswith('full-'):
        routed=jobs[jobs.gpu_model=='A10'].copy();routed['partition']='A10'
        pools={'A10':nodes[nodes.gpu_model=='A10']}
    else:pools,routed=(route_shape if spec['routing']=='R-shape' else route)(nodes,jobs,cfg)
    frames=[];rows=[];individual={}
    for key,sub in routed.groupby('partition',sort=True):
        pool=pools[key].sort_values('node_name').reset_index(drop=True)
        placement=spec['placement'].get(key,'ff-id')
        result=simulate_pool(pool,sub,spec['policy'],theta_seconds=spec['theta_seconds'],reservation_k=200,event_mode='shared-timer',diagnostics=True,placement=placement)
        frame=result['jobs'].copy();frame['start']=result['starts'];frame['finish']=result['ends'];frames.append(frame)
        rows.extend((int(jid),int(pool.node_name.iloc[i]),int(w)) for jid,plan in zip(frame.job_name,result['plans']) for i,w in plan)
        individual[key]=metrics(result,pool,cfg.horizon_seconds)
    frame=pd.concat(frames,ignore_index=True).sort_values('job_name').reset_index(drop=True)
    ledger=pd.DataFrame(rows,columns=['job_name','node_name','workers']).sort_values(['job_name','node_name']).reset_index(drop=True)
    report=individual if a.case.startswith('full-') else describe(nodes,frame,cfg)
    a.output.mkdir(parents=True)
    frame.to_csv(a.output/'jobs.csv.gz',index=False,compression='gzip')
    ledger.to_csv(a.output/'placements.csv.gz',index=False,compression='gzip')
    code_hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (PROBLEM/'src').rglob('*.py')}
    (a.output/'metrics.json').write_text(json.dumps(native({'case':a.case,'configuration':spec,'raw_hashes':hashes,'core_source_sha256':code_hashes,'metrics':report,'scope':'Reproduction output; not an independent validation or a new performance claim'}),indent=2)+'\n')
    print(f'{a.case}: wrote {len(frame)} jobs to {a.output}')

if __name__=='__main__':main()
