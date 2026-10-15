"""Frozen pre-start routing and disjoint physical partitions; reuse the existing DES.

Compatibility and sigma are scenario assumptions, never inferred performance facts.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import math

import numpy as np
import pandas as pd

from .evaluation import metrics
from .placement import slots
from .simulator import simulate_pool

SOURCE = 'A10'
TARGET = 'A100-SXM4-80GB'
FOREIGN = 'A100-foreign'
POLICIES = ('FCFS', 'SJF-HOL')


@dataclass(frozen=True)
class Config:
    donor_nodes: int = 60
    route_numerator: int = 1
    route_denominator: int = 10
    compatibility: bool = True
    sigma: float = 1
    horizon_seconds: int = 7776000
    hash_namespace: str = 'q3-fixed-split-v1'

    def __post_init__(self):
        for name in ('donor_nodes', 'route_numerator', 'route_denominator', 'horizon_seconds'):
            if type(getattr(self, name)) is not int:
                raise ValueError(f'{name} must be an integer')
        if (self.donor_nodes < 0 or self.route_denominator <= 0
                or not 0 <= self.route_numerator <= self.route_denominator
                or self.horizon_seconds <= 0):
            raise ValueError('Invalid capacity, routing fraction or horizon')
        if type(self.compatibility) is not bool or not isinstance(self.hash_namespace, str):
            raise ValueError('Invalid compatibility or namespace')
        if not math.isfinite(self.sigma) or self.sigma <= 0:
            raise ValueError('Positive finite sigma required')

    def dictionary(self):
        return asdict(self)


def selected(job_id, config):
    u = int.from_bytes(sha256(f'{config.hash_namespace}:{int(job_id)}'.encode('utf-8')).digest(), 'big')
    return config.route_denominator * u < config.route_numerator * 2**256


def fits(pool, q, c, workers):
    return int(slots(pool.gpu_capacity_num.to_numpy(), pool.cpu_units.to_numpy(), int(q), int(c)).sum()) >= workers


def route(nodes, jobs, config):
    """Pure routing: uses only this job, fixed physical capacities and frozen config."""
    target = nodes[nodes.gpu_model == TARGET].sort_values('node_name')
    active = config.compatibility and config.donor_nodes > 0
    if active and config.donor_nodes >= len(target):
        raise ValueError('Dedicated donor must leave a nonempty native target pool')
    donor = target.head(config.donor_nodes) if active else target.iloc[:0]
    pools = {m: n[~n.node_name.isin(donor.node_name)].reset_index(drop=True)
             for m, n in nodes.groupby('gpu_model', sort=True)}
    if active:
        pools[FOREIGN] = donor.reset_index(drop=True)
    frame = jobs.copy()
    frame['original_gpu_model'] = frame.gpu_model
    frame['original_duration'] = frame.duration
    frame['partition'] = frame.gpu_model
    frame['route_reason'] = 'native'
    eligible = {}
    for q, c, w in frame.loc[frame.gpu_model == SOURCE, ['gpu_request', 'cpu_units', 'worker_num']].drop_duplicates().itertuples(index=False, name=None):
        eligible[q, c, w] = active and fits(donor, q, c, w)
    for row in frame[frame.gpu_model == SOURCE].itertuples():
        if not active:
            reason = 'disabled'
        elif not eligible[row.gpu_request, row.cpu_units, row.worker_num]:
            reason = 'structurally_infeasible'
        elif not selected(row.job_name, config):
            reason = 'hash_unselected'
        else:
            reason = 'routed'
            duration = row.duration * config.sigma
            if not math.isfinite(duration) or duration != round(duration) or not 0 < duration < 2**63:
                raise ValueError('Effective duration must be positive int64 seconds; no silent rounding')
            frame.at[row.Index, 'gpu_model'] = TARGET
            frame.at[row.Index, 'duration'] = int(duration)
            frame.at[row.Index, 'partition'] = FOREIGN
        frame.at[row.Index, 'route_reason'] = reason
    # Refuse a scenario that makes any original job impossible, including native donor jobs.
    for key, sub in frame.groupby('partition'):
        pool = pools[key]
        for q, c, w in sub[['gpu_request', 'cpu_units', 'worker_num']].drop_duplicates().itertuples(index=False, name=None):
            if not fits(pool, q, c, w):
                raise ValueError(f'Empty-pool infeasibility in {key}; no jobs dropped')
    return pools, frame


def simulate(nodes, jobs, policy, config):
    pools, routed = route(nodes, jobs, config)
    frames, ledger = [], []
    for key, sub in routed.groupby('partition', sort=True):
        pool = pools[key].sort_values('node_name').reset_index(drop=True)
        result = simulate_pool(pool, sub, policy)
        frame = result['jobs'].copy()
        frame['start'], frame['finish'] = result['starts'], result['ends']
        frames.append(frame)
        for jid, plan in zip(frame.job_name, result['plans']):
            ledger.extend((int(jid), int(pool.node_name.iloc[i]), int(w)) for i, w in plan)
    return (pd.concat(frames, ignore_index=True).sort_values('job_name').reset_index(drop=True),
            pd.DataFrame(ledger, columns=['job_name', 'node_name', 'workers']).sort_values(['job_name', 'node_name']).reset_index(drop=True))


def timing(frame, horizon):
    """Cohorts use original IDs; capacity denominators belong only to physical pools."""
    if frame.empty:
        return {'jobs': 0}
    wait = (frame.start - frame.submit_time).to_numpy()
    jct = (frame.finish - frame.submit_time).to_numpy()
    out = {'jobs': len(frame), 'completed_at_horizon': int((frame.finish <= horizon).sum())}
    for name, values in [('wait', wait), ('jct', jct)]:
        for label, value in [('mean', np.mean(values)), ('median', np.median(values)),
                             ('p95', np.quantile(values, .95)), ('p99', np.quantile(values, .99)), ('max', np.max(values))]:
            out[f'{label}_{name}_hours'] = float(value / 3600)
    return out


def describe(nodes, frame, config):
    h = config.horizon_seconds
    cohorts = {'original_A10': frame.original_gpu_model == SOURCE,
               'native_A100': frame.original_gpu_model == TARGET,
               'routed_A10': frame.route_reason == 'routed',
               'unrouted_A10': (frame.original_gpu_model == SOURCE) & (frame.route_reason != 'routed'),
               'ALL': np.ones(len(frame), dtype=bool)}
    out = {'cohorts': {k: timing(frame[v], h) for k, v in cohorts.items()}, 'physical': {}}
    donor_ids = (nodes[nodes.gpu_model == TARGET].sort_values('node_name').head(config.donor_nodes).node_name
                 if config.compatibility and config.donor_nodes else [])
    physical = {m: n for m, n in nodes.groupby('gpu_model')}
    physical['ALL'] = nodes
    # Native and foreign donor denominators are explicit, including an empty foreign queue.
    if len(donor_ids):
        physical[TARGET] = physical[TARGET][~physical[TARGET].node_name.isin(donor_ids)]
        physical[FOREIGN] = nodes[nodes.node_name.isin(donor_ids)]
    for key, pool in physical.items():
        sub = frame if key == 'ALL' else frame[frame.partition == key]
        overlap = np.maximum(0, np.minimum(sub.finish.to_numpy(), h) - sub.start.to_numpy())
        gpu_sec = float(np.sum(overlap * sub.worker_num * sub.gpu_request))
        cpu_sec = float(np.sum(overlap * sub.worker_num * sub.cpu_request))
        entry = {'nodes': len(pool), 'gpus': int(pool.gpu_capacity_num.sum()),
                 'cpus': float(pool.cpu_num.sum()),
                 'gpu_allocation_rate_at_horizon': gpu_sec / (h * pool.gpu_capacity_num.sum()),
                 'cpu_allocation_rate_at_horizon': cpu_sec / (h * pool.cpu_num.sum()),
                 'full_gpu_hours': float(np.sum(sub.duration * sub.worker_num * sub.gpu_request) / 3600),
                 'full_cpu_hours': float(np.sum(sub.duration * sub.worker_num * sub.cpu_request) / 3600),
                 'window_idle_gpu_hours': float((h * pool.gpu_capacity_num.sum() - gpu_sec) / 3600)}
        if not sub.empty:
            entry['shared_evaluator'] = metrics({'jobs': sub, 'starts': sub.start.to_numpy(), 'ends': sub.finish.to_numpy()}, pool, h)
        out['physical'][key] = entry
    out['makespan_days'] = float(frame.finish.max() / 86400)
    out['routing'] = {'counts': {str(k): int(v) for k, v in frame.route_reason.value_counts().items()},
                      'original_A10_gpu_work_fraction_routed': float(
                          (frame.loc[cohorts['routed_A10'], 'original_duration'] * frame.loc[cohorts['routed_A10'], 'worker_num'] * frame.loc[cohorts['routed_A10'], 'gpu_request']).sum()
                          / (frame.loc[cohorts['original_A10'], 'original_duration'] * frame.loc[cohorts['original_A10'], 'worker_num'] * frame.loc[cohorts['original_A10'], 'gpu_request']).sum()) if cohorts['original_A10'].any() else 0.0}
    return out


def compare(baseline, treatment, horizon):
    b = baseline.set_index('job_name').sort_index()
    t = treatment.set_index('job_name').sort_index()
    if not b.index.equals(t.index):
        raise AssertionError('Counterfactual ID sets differ')
    out = {}
    for name, mask in [('original_A10', b.original_gpu_model == SOURCE),
                       ('native_A100', b.original_gpu_model == TARGET), ('ALL', np.ones(len(b), dtype=bool))]:
        x, y = b[mask], t[mask]
        dw = (y.start - x.start).to_numpy()
        de = (y.finish - x.finish).to_numpy()
        out[name] = {'jobs': len(x), 'mean_delta_wait_hours': float(dw.mean()/3600),
                     'mean_delta_jct_hours': float(de.mean()/3600),
                     'positive_extra_wait_hours': float(np.maximum(dw, 0).sum()/3600),
                     'p99_delta_wait_hours': float(np.quantile(dw, .99)/3600),
                     'max_delta_wait_hours': float(dw.max()/3600),
                     'baseline_zero_new_delay_jobs': int(((x.start == x.submit_time) & (y.start > y.submit_time)).sum()),
                     'later_completion_jobs': int((de > 0).sum()), 'earlier_completion_jobs': int((de < 0).sum()),
                     'equal_completion_jobs': int((de == 0).sum()),
                     'positive_completion_delay_hours': float(np.maximum(de, 0).sum()/3600),
                     'completion_count_delta_at_horizon': int((y.finish <= horizon).sum() - (x.finish <= horizon).sum())}
    return out
