#!/usr/bin/env python3
"""GS1-V2-R1: strict old replay, exactly two bounded ratio runs, saved-data analysis."""
import argparse
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import numpy as np
import pandas as pd
from run_gs1_placement_matrix import PROBLEM, REPO, dump, sha, run_one, replay_ledger, pair_summary
from gpu_scheduling.data import read_data
from gpu_scheduling.evaluation import metrics

H=7776000
OLD=REPO/'results/20261017-b-gs1-placement-v2-04'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--child',choices=['FCFS-HOL','SPT-HOL'])
    args=ap.parse_args()
    nodes,jobs,hashes=read_data(PROBLEM/'data/raw')
    pool=nodes[nodes.gpu_model=='GPU-series-1'].sort_values('node_name').reset_index(drop=True)
    jobs=jobs[jobs.gpu_model=='GPU-series-1'].sort_values(['submit_time','job_name']).reset_index(drop=True)
    assert (len(pool),len(jobs))==(989,9643)
    if args.child:
        run_one(pool,jobs,args.child,'ratio',None,604800,args.out,H)
        dump(args.out/(args.child.lower()+'-process-cost.json'), {'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
        return
    args.out.mkdir(parents=True,exist_ok=True)
    if (args.out/'old-replay.json').exists(): raise ValueError('Revision already started; never rerun automatically')
    old_hash={p.name:sha(p) for p in sorted(OLD.iterdir()) if p.is_file()}
    assert json.loads((OLD/'manifest.json').read_text())['data_sha256']==hashes
    code_files=list((PROBLEM/'src').rglob('*.py'))+[Path(__file__),PROBLEM/'experiments/run_gs1_placement_matrix.py']
    manifest={'revision':'GS1-V2-R1','source_commit':'a20d73f1f63a0ce45715ce8137bdef16e58e0204',
              'base_tag':'2026-mcm-b-baseline-v1','old_sha256':old_hash,'data_sha256':hashes,
              'source_sha256':{str(p.relative_to(REPO)):sha(p) for p in code_files},
              'horizon_old':7767629,'horizon_new':H,'cpu_units':'0.01 vCPU',
              'jobs':len(jobs),'nodes':len(pool),'event_mode':'shared-timer','theta_seconds':604800,
              'initial_state':'empty','drain':'complete','full_runs_limit':2,
              'timeout_seconds':900,'rss_limit_bytes':4*1024**3,
              'command':sys.argv,'environment':{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'platform':platform.platform()},
              'status':'RUNNING'}
    dump(args.out/'manifest.json',manifest)
    old_replay={}
    for t in sorted(OLD.glob('*-job-times.csv.gz')):
        name=t.name.removesuffix('-job-times.csv.gz')
        old_replay[name]=replay_ledger(pool,jobs,t,OLD/(name+'-placements.csv.gz'))
    dump(args.out/'old-replay.json',old_replay)
    if any(x['status']!='PASS' for x in old_replay.values()):
        manifest['status']='BLOCKED_OLD_REPLAY';dump(args.out/'manifest.json',manifest);raise RuntimeError('Invalid old output; no dependent experiments')
    print('PASS strict replay of all eight original runs',flush=True)
    costs={}
    for policy in ['FCFS-HOL','SPT-HOL']:
        cmd=[sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),'--child',policy]
        start=time.monotonic(); peak=0; status='PASS'
        with (args.out/(policy.lower()+'-run.log')).open('w') as log:
            proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
            while proc.poll() is None:
                try:
                    fields=Path(f'/proc/{proc.pid}/status').read_text().splitlines()
                    rss=int(next(line.split()[1] for line in fields if line.startswith('VmRSS:')))*1024
                    peak=max(peak,rss)
                except (FileNotFoundError,StopIteration): pass
                if time.monotonic()-start>900 or peak>4*1024**3:
                    status='TIMEOUT' if time.monotonic()-start>900 else 'RSS_LIMIT';proc.kill();proc.wait();break
                time.sleep(.02)
        if proc.returncode!=0 and status=='PASS': status='FAIL'
        costfile=args.out/(policy.lower()+'-process-cost.json')
        exact_peak=json.loads(costfile.read_text())['peak_rss_kib']*1024 if costfile.exists() else peak
        costs[policy]={'status':status,'command':cmd,'wall_seconds':time.monotonic()-start,'sampled_peak_rss_bytes':peak,'peak_rss_bytes':exact_peak,'returncode':proc.returncode}
        dump(args.out/'costs.json',costs)
        if status!='PASS': raise RuntimeError('Stop dependent runs: '+status)
        name=policy.lower()+'-ratio-seedid'
        verified=replay_ledger(pool,jobs,args.out/(name+'-job-times.csv.gz'),args.out/(name+'-placements.csv.gz'))
        dump(args.out/(name+'-strict-replay.json'),verified)
        if verified['status']!='PASS': raise RuntimeError('Stop dependent runs: new replay failed')
        print('PASS new ratio and strict replay:',policy,flush=True)
    records=[]; changes={}; table=[]
    for folder,label in [(OLD,'original'),(args.out,'corrected')]:
        for t in sorted(folder.glob('*-job-times.csv.gz')):
            name=t.name.removesuffix('-job-times.csv.gz');frame=pd.read_csv(t).set_index('job_name').loc[jobs.job_name].reset_index()
            schedule={'jobs':jobs,'starts':frame.start.to_numpy(),'ends':frame.finish.to_numpy()}
            before=metrics(schedule,pool,7767629);after=metrics(schedule,pool,H)
            for key in ['mean_wait_hours','p99_wait_hours','max_wait_hours','mean_jct_hours']:
                assert before[key]==after[key]
            summary=json.loads((folder/(name+'-summary.json')).read_text())
            records.append({'run':name,'version':label,'timing_sha256':sha(t),'placement_sha256':sha(folder/(name+'-placements.csv.gz')),'old_window':before,'ninety_days':after})
            policy=summary['policy'];ff=pd.read_csv(OLD/(policy.lower()+'-ff-id-seedid-job-times.csv.gz')).set_index('job_name').loc[jobs.job_name]
            delta=frame.start.to_numpy()-ff.start.to_numpy()
            row={'version':label,'policy':policy,'placement':summary['placement'],'seed':summary['seed'],**after,
                 'zero_wait_count':int((frame.start.to_numpy()==jobs.submit_time.to_numpy()).sum()),'improved_jobs':int((delta<0).sum()),'worsened_jobs':int((delta>0).sum()),'positive_added_wait_hours':float(np.maximum(delta,0).sum()/3600),
                 'scheduler_seconds':summary['runtime_seconds'],'peak_rss_bytes':costs[policy]['peak_rss_bytes'] if label=='corrected' else None,
                 'timing_sha256':sha(t)}
            table.append(row)
            if label=='corrected':
                old=pd.read_csv(OLD/t.name).set_index('job_name').loc[jobs.job_name]
                new_pl=pd.read_csv(folder/(name+'-placements.csv.gz')).sort_values(['job_name','node_name']).reset_index(drop=True)
                old_pl=pd.read_csv(OLD/(name+'-placements.csv.gz')).sort_values(['job_name','node_name']).reset_index(drop=True)
                def mapping(df): return {int(j):tuple(g[['node_name','workers']].itertuples(index=False,name=None)) for j,g in df.groupby('job_name')}
                m1,m2=mapping(old_pl),mapping(new_pl)
                changes[policy]={'timing_changed_jobs':int(((frame.start.to_numpy()!=old.start.to_numpy())|(frame.finish.to_numpy()!=old.finish.to_numpy())).sum()),'placement_changed_jobs':sum(m1[j]!=m2[j] for j in m1),'old_timing_sha256':sha(OLD/t.name),'new_timing_sha256':sha(t),'old_placement_sha256':sha(OLD/(name+'-placements.csv.gz')),'new_placement_sha256':sha(folder/(name+'-placements.csv.gz'))}
                pair_summary(ff.reset_index(),frame,policy,args.out)
                pairs=frame[['job_name','start','finish']].copy();pairs['ff_wait_seconds']=ff.start.to_numpy()-jobs.submit_time.to_numpy();pairs['ratio_wait_seconds']=frame.start.to_numpy()-jobs.submit_time.to_numpy();pairs['delta_seconds']=delta
                pairs.to_csv(args.out/(policy.lower()+'-paired.csv.gz'),index=False)
    dump(args.out/'window-comparison.json',records);dump(args.out/'fallback-changes.json',changes)
    pd.DataFrame(table).to_csv(args.out/'comparison.csv',index=False)
    dump(args.out/'comparison.json',table)
    assert old_hash=={p.name:sha(p) for p in OLD.iterdir() if p.is_file()}
    manifest['status']='PASS';manifest['old_files_unchanged']=True
    manifest['outputs_sha256']={p.name:sha(p) for p in args.out.iterdir() if p.is_file() and p.name!='manifest.json'}
    dump(args.out/'manifest.json',manifest)

if __name__=='__main__': main()
