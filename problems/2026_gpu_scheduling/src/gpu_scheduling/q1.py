"""Q1 audited handoff computations: a single source for both EDA entry points.

All demand below is counterfactual immediate-start demand, never allocation.
The floor top-k convention differs from the older independent audit's ceil
convention; do not combine the two concentration tables without recomputation.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .data import CPU_SCALE, read_data

SECOND_PER_HOUR = 3600
SECOND_PER_DAY = 86400
MODEL_ORDER = ['A10', 'A100-SXM4-80GB', 'GPU-series-1', 'H800', 'GPU-series-2', 'A800-SXM4-80GB']

def load_data(source: Path):
    nodes, jobs, hashes = read_data(source)
    # Q1 copies share the baseline's checked byte loader; Q2/Q3 never receive
    # these derived work or counterfactual-demand columns.
    nodes = nodes.rename(columns={"cpu_units": "cpu_scaled"})
    jobs = jobs.rename(columns={"cpu_units": "cpu_scaled"})
    if jobs.submit_time.min() != 0:
        raise ValueError("Expected trace origin at zero; do not silently rebase it")
    jobs["total_gpu"] = jobs.gpu_request * jobs.worker_num
    jobs["total_cpu_scaled"] = jobs.cpu_scaled * jobs.worker_num
    jobs["total_cpu"] = jobs.total_cpu_scaled / CPU_SCALE
    jobs["gpu_seconds"] = jobs.total_gpu * jobs.duration
    jobs["gpu_hours"] = jobs.gpu_seconds / SECOND_PER_HOUR
    jobs["cpu_hours"] = jobs.total_cpu_scaled * jobs.duration / (CPU_SCALE * SECOND_PER_HOUR)
    jobs["cpu_per_gpu"] = jobs.cpu_request / jobs.gpu_request
    return nodes, jobs, hashes


def gini(values):
    """Uncorrected empirical Gini, as in the original eda_deep.py."""
    x = np.sort(np.asarray(values, dtype=float))
    if len(x) == 0 or not np.isfinite(x).all() or (x < 0).any() or x.sum() <= 0:
        raise ValueError('Gini requires nonempty nonnegative data with positive sum')
    rank = np.arange(1, len(x) + 1, dtype=float)
    return float(np.dot(2 * rank - len(x) - 1, x) / (len(x) * x.sum()))


def top_share(values, fraction):
    """Floor count preserves the original EDA convention; report k explicitly."""
    x = np.sort(np.asarray(values, dtype=float))[::-1]
    k = int(np.floor(len(x) * fraction))
    return k, float(x[:k].sum() / x.sum())


def lorenz(values):
    x = np.sort(np.asarray(values, dtype=float))
    return np.arange(len(x) + 1) / len(x), np.r_[0., np.cumsum(x) / x.sum()]


def ccdf(values):
    """Exact strict empirical P(X > x), grouping ties before calculation."""
    x, counts = np.unique(np.asarray(values), return_counts=True)
    return x, 1 - np.cumsum(counts) / counts.sum()


def demand_timeline(arrival, duration, quantity, horizon):
    """Counterfactual immediate-start demand on half-open [0,T); NOT allocation."""
    a, p, q = [np.asarray(v, dtype=np.int64) for v in (arrival, duration, quantity)]
    valid = (a < horizon) & (a + p > 0)
    start = np.maximum(a[valid], 0)
    stop = np.minimum(a[valid] + p[valid], horizon)
    t = np.r_[0, horizon, start, stop]
    delta = np.r_[0, 0, q[valid], -q[valid]]
    edges, inv = np.unique(t, return_inverse=True)
    changes = np.zeros(len(edges), dtype=np.int64)
    np.add.at(changes, inv, delta)
    value = np.cumsum(changes)
    if value[-1] != 0 or np.any(value < 0):
        raise AssertionError('Immediate-start demand event accounting failed')
    area = int(np.dot(value[:-1], np.diff(edges)))
    direct = int(np.dot(q, np.maximum(0, np.minimum(a + p, horizon) - np.maximum(a, 0))))
    if area != direct:
        raise AssertionError('Event integral disagrees with direct interval overlap')
    return edges, value[:-1], area


def phase_exposure(horizon):
    cycles, remainder = divmod(horizon, SECOND_PER_DAY)
    return cycles + np.clip(remainder - np.arange(24) * SECOND_PER_HOUR, 0, SECOND_PER_HOUR) / SECOND_PER_HOUR


def empty_pool_fit(nodes, grp):
    configs = nodes.groupby(['gpu_capacity_num', 'cpu_scaled']).size()
    capacity = np.zeros(len(grp), dtype=np.int64)
    q, c = grp.gpu_request.to_numpy(), grp.cpu_scaled.to_numpy()
    for (gpu, cpu), count in configs.items():
        h = gpu // q
        positive = c > 0
        h[positive] = np.minimum(h[positive], cpu // c[positive])
        capacity += h * count
    return capacity >= grp.worker_num.to_numpy()


def save_csv(df, out, name):
    df.to_csv(out / name, index=False, encoding='utf-8-sig', float_format='%.12g')


def analyze(source: Path, out: Path):
    nodes, jobs, hashes = load_data(source)
    T = int(jobs.submit_time.max())
    if T <= 0:
        raise ValueError('Positive observation window required')
    out.mkdir(parents=True, exist_ok=False)
    configs = nodes.groupby(['gpu_model','gpu_capacity_num','cpu_num']).size().reset_index(name='nodes')
    save_csv(configs, out, 'node_configurations.csv')
    summary, demand, ratios, bymodel = [], [], [], []
    ordered = [m for m in MODEL_ORDER if m in set(nodes.gpu_model)] + sorted(set(nodes.gpu_model) - set(MODEL_ORDER))
    for model in ordered:
        nd = nodes[nodes.gpu_model == model]
        j = jobs[jobs.gpu_model == model]
        if j.empty:
            continue
        B = int(nd.gpu_capacity_num.sum()); C = float(nd.cpu_num.sum())
        z = j[j.submit_time == 0]
        row = dict(gpu_model=model, nodes=len(nd), physical_gpus=B, vcpus=C, jobs=len(j),
                   capacity_share=float(B/nodes.gpu_capacity_num.sum()), job_share=float(len(j)/len(jobs)),
                   gpu_hours=float(j.gpu_hours.sum()), work_share=float(j.gpu_hours.sum()/jobs.gpu_hours.sum()),
                   cpu_hours=float(j.cpu_hours.sum()), rho_gpu=float(j.gpu_seconds.sum()/(T*B)),
                   rho_cpu=float(j.cpu_hours.sum()/(T/SECOND_PER_HOUR*C)),
                   rho_gpu_nominal_90d=float(j.gpu_seconds.sum()/(90*SECOND_PER_DAY*B)),
                   mean_workers=float(j.worker_num.mean()), max_workers=int(j.worker_num.max()),
                   mean_gpu_per_worker=float(j.gpu_request.mean()), max_gpu_per_job=int(j.total_gpu.max()),
                   single_worker_fraction=float((j.worker_num==1).mean()),
                   one_gpu_per_worker_fraction=float((j.gpu_request==1).mean()),
                   median_duration_seconds=float(j.duration.median()), mean_duration_hours=float(j.duration.mean()/3600),
                   p95_duration_hours=float(j.duration.quantile(.95)/3600),
                   t0_jobs=len(z), t0_gpu_hours=float(z.gpu_hours.sum()), t0_work_share=float(z.gpu_hours.sum()/j.gpu_hours.sum()),
                   infeasible_empty_pool_jobs=int((~empty_pool_fit(nd,j)).sum()),
                   gini_work=gini(j.gpu_seconds), gini_duration=gini(j.duration))
        summary.append(row)
        for res, quantity, cap in [('GPU',j.total_gpu,B), ('CPU',j.total_cpu_scaled,int(nd.cpu_scaled.sum()))]:
            edges, val, area = demand_timeline(j.submit_time,j.duration,quantity,T)
            scale = 1 if res=='GPU' else CPU_SCALE
            demand.append(dict(gpu_model=model,resource=res,capacity=cap/scale,
                immediate_start_mean=area/T/scale,immediate_start_mean_ratio=area/T/cap,
                immediate_start_peak=float(val.max()/scale),
                time_above_capacity_seconds=int(np.diff(edges)[val>cap].sum()),
                fraction_time_above_capacity=float(np.diff(edges)[val>cap].sum()/T),
                window_requested_resource_hours=area/scale/3600))
        for c in configs[configs.gpu_model==model].itertuples(index=False):
            threshold=c.cpu_num/c.gpu_capacity_num
            high=j.cpu_per_gpu>threshold
            ratios.append(dict(gpu_model=model,gpus_per_node=c.gpu_capacity_num,vcpus_per_node=c.cpu_num,
                nodes=c.nodes,node_cpu_per_gpu=threshold,jobs_above_ratio=int(high.sum()),
                fraction_jobs_above_ratio=float(high.mean()),work_share_above_ratio=float(j.loc[high,'gpu_hours'].sum()/j.gpu_hours.sum())))
    save_csv(pd.DataFrame(summary),out,'pool_summary.csv')
    save_csv(pd.DataFrame(demand),out,'immediate_start_demand.csv')
    save_csv(pd.DataFrame(ratios),out,'resource_shape.csv')
    concentration=[]
    for model,j in [('ALL',jobs)]+[(m,jobs[jobs.gpu_model==m]) for m in ordered]:
        if j.empty: continue
        for f in [.001,.005,.01,.05,.10,.20]:
            k,share=top_share(j.gpu_seconds,f)
            concentration.append(dict(gpu_model=model,nominal_top_fraction=f,jobs_selected=k,
                actual_top_fraction=k/len(j),work_share=share))
    save_csv(pd.DataFrame(concentration),out,'concentration.csv')
    quantiles=[]
    for q in [.05,.1,.25,.5,.75,.9,.95,.99,1.]:
        x=float(jobs.duration.quantile(q))
        quantiles.append(dict(quantile=q,duration_seconds=x,duration_hours=x/3600,duration_days=x/86400))
    save_csv(pd.DataFrame(quantiles),out,'duration_quantiles.csv')
    days=np.arange(int(np.ceil(T/86400)))
    daily=[]; blocks=[]
    for model,j in [('ALL',jobs)]+[(m,jobs[jobs.gpu_model==m]) for m in ordered]:
        di=j.submit_time//86400
        # Inclusive final arrival; here supplied T is not exactly a day boundary.
        for d in days:
            part=j[di==d]
            daily.append(dict(gpu_model=model,trace_day=int(d),exposure_seconds=int(min(T,(d+1)*86400)-d*86400),
                jobs=len(part),jobs_excluding_t0=int((part.submit_time>0).sum()),
                submitted_full_lifetime_gpu_hours=float(part.gpu_hours.sum()),
                t0_gpu_hours=float(part.loc[part.submit_time==0,'gpu_hours'].sum())))
        for begin in range(0,len(days),30):
            part=j[(di>=begin)&(di<begin+30)]
            blocks.append(dict(gpu_model=model,start_trace_day=begin,end_trace_day=min(begin+30,len(days)),
                jobs=len(part),submitted_full_lifetime_gpu_hours=float(part.gpu_hours.sum()),
                t0_gpu_hours=float(part.loc[part.submit_time==0,'gpu_hours'].sum())))
    save_csv(pd.DataFrame(daily),out,'daily_arrivals.csv')
    save_csv(pd.DataFrame(blocks),out,'thirty_day_blocks.csv')
    phases=[]
    exposure=phase_exposure(T)
    for model,j in [('ALL',jobs)]+[(m,jobs[jobs.gpu_model==m]) for m in ordered]:
        phase=((j.loc[j.submit_time>0,'submit_time']%86400)//3600).astype(int)
        counts=np.bincount(phase,minlength=24)
        for h in range(24):
            phases.append(dict(gpu_model=model,relative_phase_hour=h,jobs=int(counts[h]),
                exposure_hours=float(exposure[h]),jobs_per_exposed_hour=float(counts[h]/exposure[h])))
    phase_df=pd.DataFrame(phases);save_csv(phase_df,out,'relative_24h_phase.csv')
    ap=phase_df[phase_df.gpu_model=='ALL'];hi=ap.loc[ap.jobs_per_exposed_hour.idxmax()];lo=ap.loc[ap.jobs_per_exposed_hour.idxmin()]
    stats=dict(jobs=len(jobs),nodes=len(nodes),physical_gpus=int(nodes.gpu_capacity_num.sum()),
        vcpus=float(nodes.cpu_num.sum()),gpu_models=len(ordered),first_arrival_seconds=int(jobs.submit_time.min()),
        horizon_seconds=T,horizon_hours=T/3600,horizon_days=T/86400,
        nominal_90day_difference_seconds=90*86400-T,missing_required_values=0,duplicate_job_ids=0,duplicate_node_ids=0,
        fractional_cpu_jobs=int((jobs.cpu_request%1!=0).sum()),zero_cpu_jobs=int((jobs.cpu_request==0).sum()),
        min_duration_seconds=int(jobs.duration.min()),max_duration_seconds=int(jobs.duration.max()),
        total_gpu_hours=float(jobs.gpu_hours.sum()),total_cpu_hours=float(jobs.cpu_hours.sum()),
        mean_workers=float(jobs.worker_num.mean()),mean_gpu_per_worker=float(jobs.gpu_request.mean()),
        single_worker_jobs=int((jobs.worker_num==1).sum()),one_gpu_per_worker_jobs=int((jobs.gpu_request==1).sum()),
        t0_jobs=int((jobs.submit_time==0).sum()),t0_gpu_hours=float(jobs.loc[jobs.submit_time==0,'gpu_hours'].sum()),
        jobs_duration_longer_than_T=int((jobs.duration>T).sum()),jobs_immediate_finish_after_T=int(((jobs.submit_time+jobs.duration)>T).sum()),
        gini_gpu_work=gini(jobs.gpu_seconds),gini_duration=gini(jobs.duration),
        peak_relative_hour=int(hi.relative_phase_hour),trough_relative_hour=int(lo.relative_phase_hour),
        peak_phase_rate=float(hi.jobs_per_exposed_hour),trough_phase_rate=float(lo.jobs_per_exposed_hour),
        phase_peak_trough_ratio=float(hi.jobs_per_exposed_hour/lo.jobs_per_exposed_hour),
        top_k_rule='floor(n*f), descending full-lifetime GPU work',
        quantile_rule='linear interpolation (pandas default)',
        window_rule='[0,T), T=last submission; all supplied rows included in lifetime work',
        immediate_start_rule='start=submit_time, ignoring resource feasibility; not actual allocation',
        allocation_rate_status='NOT_IDENTIFIABLE_FROM_SUPPLIED_CSVS',input_sha256=hashes)
    (out/'q1_results.json').write_text(json.dumps(stats,indent=2,ensure_ascii=False),encoding='utf-8')
    return nodes,jobs,stats
