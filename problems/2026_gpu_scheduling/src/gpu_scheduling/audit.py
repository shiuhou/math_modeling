"""Independent raw-data accounting; full-lifetime work is not utilization."""
import math
import numpy as np
import pandas as pd
from .data import CPU_SCALE, DAY, native
from .placement import slots

def audit(nodes: pd.DataFrame, jobs: pd.DataFrame, hashes: dict) -> dict:
    a0, T = int(jobs.submit_time.min()), int(jobs.submit_time.max())
    span = T-a0
    if span <= 0: raise ValueError('Trace has no positive arrival span')
    gwork = jobs.gpu_request * jobs.worker_num * jobs.duration
    cwork = jobs.cpu_request * jobs.worker_num * jobs.duration
    types, impossible = [], 0
    for g, sub in jobs.groupby('gpu_model', sort=True):
        nd = nodes[nodes.gpu_model == g]
        G, C = int(nd.gpu_capacity_num.sum()), float(nd.cpu_num.sum())
        ss = sub[['gpu_request','cpu_units','worker_num']].drop_duplicates()
        for q,c,w in ss.itertuples(index=False, name=None):
            if slots(nd.gpu_capacity_num.to_numpy(), nd.cpu_units.to_numpy(), q, c).sum() < w:
                impossible += int(((sub.gpu_request==q)&(sub.cpu_units==c)&(sub.worker_num==w)).sum())
        Dg = int((sub.gpu_request*sub.worker_num*sub.duration).sum())
        Dc = float((sub.cpu_request*sub.worker_num*sub.duration).sum())
        latest = int((sub.submit_time+sub.duration).max())
        types.append(dict(gpu_model=g,nodes=len(nd),gpus=G,vcpus=C,jobs=len(sub),
            gpu_hours=Dg/3600,cpu_hours=Dc/3600,gpu_load_ratio=Dg/(G*span),cpu_load_ratio=Dc/(C*span),
            gpu_work_bound_days=Dg/G/DAY,arrival_service_bound_days=latest/DAY,
            combined_makespan_bound_days=max(Dg/G,Dc/C,latest)/DAY,
            duration_median_seconds=float(sub.duration.median()),
            duration_p95_seconds=float(sub.duration.quantile(.95)),
            multiworker_fraction=float((sub.worker_num>1).mean()),
            max_workers=int(sub.worker_num.max()),gpu_per_worker_max=int(sub.gpu_request.max()),
            cpu_per_worker_max=float(sub.cpu_request.max())))
    if impossible: raise ValueError(f'{impossible} jobs are infeasible on an empty cluster')
    quant = {str(q): float(jobs.duration.quantile(q)) for q in [.0,.25,.5,.75,.9,.95,.99,1.]}
    sorted_work = np.sort(gwork.to_numpy())[::-1]
    concentration = {str(f): float(sorted_work[:int(np.floor(f*len(jobs)))].sum()/sorted_work.sum()) for f in [.001,.01,.05,.1]}
    day = jobs.submit_time // DAY
    daily = pd.DataFrame({'day':day,'jobs':1,'gpu_seconds':gwork}).groupby('day').sum().reset_index()
    configs = nodes.groupby(['gpu_model','gpu_capacity_num','cpu_num']).size().reset_index(name='nodes')
    return native(dict(hashes=hashes,records=dict(nodes=len(nodes),jobs=len(jobs),gpu_types=nodes.gpu_model.nunique(),
        gpus=nodes.gpu_capacity_num.sum(),vcpus=nodes.cpu_num.sum()),
        audit=dict(missing=0,duplicate_job_ids=0,duplicate_node_ids=0,empty_cluster_infeasible_jobs=impossible,
                   fractional_cpu_jobs=int((jobs.cpu_request%1!=0).sum()),zero_cpu_jobs=int((jobs.cpu_request==0).sum()),
                   cpu_scale=CPU_SCALE,minimum_duration_seconds=int(jobs.duration.min())),
        times=dict(first_submit_seconds=a0,last_submit_seconds=T,span_seconds=span,span_days=span/DAY,
                   jobs_at_time_zero=int((jobs.submit_time==0).sum()),jobs_longer_than_arrival_span=int((jobs.duration>span).sum()),
                   maximum_earliest_finish_seconds=int((jobs.submit_time+jobs.duration).max())),
        aggregate=dict(gpu_hours=float(gwork.sum()/3600),cpu_hours=float(cwork.sum()/3600),
            nominal_gpu_load_ratio=float(gwork.sum()/(nodes.gpu_capacity_num.sum()*span)),
            nominal_cpu_load_ratio=float(cwork.sum()/(nodes.cpu_num.sum()*span)),
            duration_mean_seconds=float(jobs.duration.mean()),duration_quantiles_seconds=quant,
            single_worker_fraction=float((jobs.worker_num==1).mean()),
            maximum_job_gpus=int((jobs.worker_num*jobs.gpu_request).max()),
            concentration_top_job_fraction=concentration,concentration_top_k_rule="floor(n*f), descending full-lifetime GPU work"),
        per_gpu_type=types,node_configurations=configs.to_dict('records'),daily=daily.to_dict('records')))
