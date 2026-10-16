"""Shared metric calculation; metric values do not certify capacity feasibility."""
import numpy as np
import pandas as pd
from .data import DAY, native

def metrics(result: dict,nodes: pd.DataFrame,horizon: int) -> dict:
    j=result['jobs'];s=result['starts'];e=result['ends']
    if horizon<=0 or len(j)==0 or len(s)!=len(j) or len(e)!=len(j):
        raise ValueError('Metrics require jobs, matching timing arrays and a positive horizon')
    if not np.isfinite(s).all() or not np.isfinite(e).all() or not np.all(s>=j.submit_time.to_numpy()) or not np.all(e-s==j.duration.to_numpy()):
        raise ValueError('Invalid timing; capacity feasibility is checked separately')
    w=s-j.submit_time.to_numpy();p=j.duration.to_numpy()
    overlap=np.minimum(p,np.maximum(horizon-s,0))
    # Standard bounded slowdown is at least one, including jobs shorter than tau.
    bs=np.maximum(1.,(w+p)/np.maximum(p,60))
    return native(dict(jobs=len(j),mean_wait_hours=w.mean()/3600,median_wait_hours=np.median(w)/3600,
        p95_wait_hours=np.quantile(w,.95)/3600,p99_wait_hours=np.quantile(w,.99)/3600,
        max_wait_hours=w.max()/3600,mean_jct_hours=np.mean(e-j.submit_time.to_numpy())/3600,
        zero_wait_fraction=np.mean(w==0),mean_bounded_slowdown_60s=np.mean(bs),p99_bounded_slowdown_60s=np.quantile(bs,.99),
        completed_at_horizon=np.sum(e<=horizon),gpu_allocation_rate_at_horizon=float(np.sum(overlap*j.worker_num*j.gpu_request)/(horizon*nodes.gpu_capacity_num.sum())),
        cpu_allocation_rate_at_horizon=float(np.sum(overlap*j.worker_num*j.cpu_request)/(horizon*nodes.cpu_num.sum())),
        final_completion_days=e.max()/DAY))
