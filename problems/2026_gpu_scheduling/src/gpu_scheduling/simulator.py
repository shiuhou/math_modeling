"""One active event engine: strict per-model FCFS and SJF-HOL, first-fit."""
import heapq
import math
from collections import deque
import numpy as np
import pandas as pd
from .placement import slots
from .validation import validate

def simulate_pool(nodes: pd.DataFrame, jobs: pd.DataFrame, policy: str) -> dict:
    """Online arrivals, known submitted durations, identical workers, first-fit nodes."""
    if policy not in ('FCFS','SJF-HOL'): raise ValueError(policy)
    nodes=nodes.sort_values('node_name',kind='stable').reset_index(drop=True)
    jobs=jobs.sort_values(['submit_time','job_name'],kind='stable').reset_index(drop=True)
    if nodes.empty or jobs.empty:
        raise ValueError('A pool must contain nodes and jobs')
    if nodes.gpu_model.nunique()!=1 or jobs.gpu_model.nunique()!=1 or nodes.gpu_model.iloc[0]!=jobs.gpu_model.iloc[0]:
        raise ValueError('simulate_pool requires one matching GPU model')
    n=len(jobs)
    arr=jobs.submit_time.to_numpy(dtype=np.int64)
    dur=jobs.duration.to_numpy(dtype=np.int64)
    reqg=jobs.gpu_request.to_numpy(dtype=np.int64)
    reqc=jobs.cpu_units.to_numpy(dtype=np.int64)
    workers=jobs.worker_num.to_numpy(dtype=np.int64)
    capg=nodes.gpu_capacity_num.to_numpy(dtype=np.int64); capc=nodes.cpu_units.to_numpy(dtype=np.int64)
    for q,c,w in jobs[['gpu_request','cpu_units','worker_num']].drop_duplicates().itertuples(index=False,name=None):
        if slots(capg,capc,int(q),int(c)).sum()<int(w):
            raise ValueError('Job infeasible on an empty pool; no jobs were dropped')
    fg=capg.copy();fc=capc.copy()
    starts=np.full(n,-1,dtype=np.int64);ends=np.full(n,-1,dtype=np.int64)
    plans=[None]*n
    wait=deque() if policy=='FCFS' else []
    running=[]; k=0; finished=0; decisions=0; peak_queue=0
    while k<n or wait or running:
        t=min(int(arr[k]) if k<n else math.inf, running[0][0] if running else math.inf)
        if not math.isfinite(t): raise RuntimeError('Stuck queue: no future event')
        t=int(t)
        while running and running[0][0]==t:
            _, j=heapq.heappop(running)
            for m,w in plans[j]:
                fg[m]+=w*reqg[j];fc[m]+=w*reqc[j]
                if fg[m]>capg[m] or fc[m]>capc[m]: raise AssertionError('Over-release')
            finished+=1
        while k<n and arr[k]==t:
            if policy=='FCFS': wait.append(k)
            else: heapq.heappush(wait,(int(dur[k]),int(arr[k]),int(jobs.job_name.iloc[k]),k))
            k+=1
        peak_queue=max(peak_queue,len(wait))
        while wait:
            j=wait[0] if policy=='FCFS' else wait[0][3]
            h=slots(fg,fc,int(reqg[j]),int(reqc[j]));decisions+=1
            if int(h.sum())<int(workers[j]): break
            todo=int(workers[j]);plan=[]
            for m in np.flatnonzero(h):
                take=min(todo,int(h[m]));plan.append((int(m),take));todo-=take
                if todo==0:break
            if todo:raise AssertionError('Feasibility/placement mismatch')
            # Atomic commit: no resource state has been changed while planning.
            for m,w in plan:
                fg[m]-=w*reqg[j];fc[m]-=w*reqc[j]
                if fg[m]<0 or fc[m]<0:raise AssertionError('Capacity violation')
            plans[j]=plan;starts[j]=t;ends[j]=t+dur[j]
            if policy=='FCFS':wait.popleft()
            else:heapq.heappop(wait)
            heapq.heappush(running,(int(ends[j]),j))
    assert finished==n and np.array_equal(fg,capg) and np.array_equal(fc,capc)
    validate(nodes,jobs,starts,ends,plans)
    return dict(jobs=jobs,starts=starts,ends=ends,plans=plans,feasibility_checks=decisions,peak_queue=peak_queue)
