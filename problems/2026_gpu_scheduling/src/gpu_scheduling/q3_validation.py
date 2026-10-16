"""Independent raw-input/routing audit plus persisted physical ledger replay.

Does not call the routing producer or simulate a second schedule. Checks physical
feasibility, not optimality; policy regression is checked against baseline output.
"""
import hashlib
import math

import numpy as np
import pandas as pd

from .validation import validate


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def verify_schedule(nodes, original, frame, ledger, config):
    require(not frame.job_name.duplicated().any(), 'Duplicate job IDs')
    raw = original.set_index('job_name').sort_index()
    saved = frame.set_index('job_name').sort_index()
    require(raw.index.equals(saved.index), 'Missing or extra original IDs')
    for col in raw.columns:
        expected = 'original_gpu_model' if col == 'gpu_model' else 'original_duration' if col == 'duration' else col
        pd.testing.assert_series_equal(raw[col], saved[expected], check_names=False, check_dtype=False)
    for table, cols in [(frame, ['job_name', 'duration', 'start', 'finish']),
                        (ledger, ['job_name', 'node_name', 'workers'])]:
        for col in cols:
            v = table[col].to_numpy(dtype=float)
            require(np.isfinite(v).all() and (v == np.floor(v)).all() and (np.abs(v) < 2**63).all(), f'Invalid integer {col}')
    require(not ledger.duplicated(['job_name', 'node_name']).any(), 'Duplicate placement pair')
    require(set(ledger.job_name) == set(raw.index), 'Ledger job IDs')
    require(set(ledger.node_name) <= set(nodes.node_name), 'Unknown physical nodes')
    active = config.compatibility and config.donor_nodes > 0
    target = nodes[nodes.gpu_model == 'A100-SXM4-80GB'].sort_values('node_name')
    require(not active or config.donor_nodes < len(target), 'No native donor pool')
    donor = target.head(config.donor_nodes) if active else target.iloc[:0]
    donor_ids = set(donor.node_name)
    shape_cache = {}
    for j in saved.itertuples():
        source = raw.loc[j.Index]
        if source.gpu_model != 'A10':
            reason = 'native'
        elif not active:
            reason = 'disabled'
        else:
            shape = (source.gpu_request, source.cpu_units, source.worker_num)
            if shape not in shape_cache:
                available = sum(min(int(n.gpu_capacity_num)//int(source.gpu_request),
                                    int(n.cpu_units)//int(source.cpu_units) if source.cpu_units else int(n.gpu_capacity_num)//int(source.gpu_request))
                                for n in donor.itertuples())
                shape_cache[shape] = available >= source.worker_num
            digest = hashlib.sha256((config.hash_namespace + ':' + str(int(j.Index))).encode('utf-8')).hexdigest()
            chosen = int(digest, 16) * config.route_denominator < config.route_numerator * (1 << 256)
            reason = 'structurally_infeasible' if not shape_cache[shape] else 'routed' if chosen else 'hash_unselected'
        routed = reason == 'routed'
        require(j.route_reason == reason, 'Routing reason')
        require(j.partition == ('A100-foreign' if routed else source.gpu_model), 'Partition')
        require(j.gpu_model == ('A100-SXM4-80GB' if routed else source.gpu_model), 'Actual GPU model')
        require(j.duration == source.duration * (config.sigma if routed else 1), 'Effective duration')
    partition = saved.partition.to_dict()
    for job_id, node_id in ledger[['job_name', 'node_name']].itertuples(index=False, name=None):
        require((node_id in donor_ids) == (partition[job_id] == 'A100-foreign'), 'Physical partition isolation')
    ordered_nodes = nodes.sort_values('node_name').reset_index(drop=True)
    ordered_jobs = saved.reset_index()
    ni = {int(v): i for i, v in enumerate(ordered_nodes.node_name)}
    ji = {int(v): i for i, v in enumerate(ordered_jobs.job_name)}
    plans = [[] for _ in range(len(ordered_jobs))]
    for j, n, w in ledger.itertuples(index=False, name=None):
        require(w > 0, 'Positive integer workers')
        plans[ji[int(j)]].append((ni[int(n)], int(w)))
    validate(ordered_nodes, ordered_jobs, ordered_jobs.start.to_numpy(), ordered_jobs.finish.to_numpy(), plans)
    # Queue integral from event counts, independently of the duration sum formula.
    events = pd.concat([pd.DataFrame({'t': frame.submit_time, 'd': 1}), pd.DataFrame({'t': frame.start, 'd': -1})])
    changes = events.groupby('t').d.sum().sort_index()
    q = 0; previous = 0; area = 0
    for t, delta in changes.items():
        area += q * (int(t) - previous)
        q += int(delta); previous = int(t)
        require(q >= 0, 'Negative queue size')
    require(q == 0 and area == int((frame.start-frame.submit_time).sum()), 'Queue integral identity')
    joined = ledger.merge(frame[['job_name', 'duration', 'gpu_request', 'cpu_units', 'worker_num']], on='job_name', validate='many_to_one')
    for resource in ['gpu_request', 'cpu_units']:
        require(int((joined.duration*joined.workers*joined[resource]).sum()) == int((frame.duration*frame.worker_num*frame[resource]).sum()), 'Full resource work identity')
    return {'status': 'PASS', 'original_jobs': len(raw),
            'native_A100_jobs': int((raw.gpu_model == 'A100-SXM4-80GB').sum()),
            'placements': len(ledger), 'donor_nodes': len(donor), 'borrowed_gpu_cap': int(donor.gpu_capacity_num.sum()),
            'queue_integral_job_seconds': area, 'physical_node_replay': 'PASS', 'routing_from_raw': 'PASS',
            'job_identity_and_attributes': 'PASS', 'resource_work_identity': 'PASS'}


def verify_metrics(nodes, frame, config, report):
    """Independent scalar/group aggregation; never invokes the metrics producer."""
    def close(actual, expected, label):
        require(math.isclose(float(actual), float(expected), rel_tol=1e-11, abs_tol=1e-10), 'Metric mismatch: ' + label)
    h = config.horizon_seconds
    masks = {'original_A10': frame.original_gpu_model == 'A10',
             'native_A100': frame.original_gpu_model == 'A100-SXM4-80GB',
             'routed_A10': frame.route_reason == 'routed',
             'unrouted_A10': (frame.original_gpu_model == 'A10') & (frame.route_reason != 'routed'),
             'ALL': pd.Series(True, index=frame.index)}
    for key, mask in masks.items():
        sub = frame[mask]; entry = report['cohorts'][key]
        close(entry['jobs'], len(sub), key)
        if sub.empty:
            continue
        close(entry['completed_at_horizon'], sum(sub.finish <= h), key)
        for metric, values in [('wait', sub.start-sub.submit_time), ('jct', sub.finish-sub.submit_time)]:
            for label, value in [('mean', values.sum()/len(values)), ('median', values.quantile(.5)),
                                 ('p95', values.quantile(.95)), ('p99', values.quantile(.99)), ('max', values.max())]:
                close(entry[f'{label}_{metric}_hours'], value/3600, key + metric + label)
    active = config.compatibility and config.donor_nodes > 0
    donor = set(nodes[nodes.gpu_model == 'A100-SXM4-80GB'].sort_values('node_name').head(config.donor_nodes).node_name) if active else set()
    expected_keys = set(nodes.gpu_model) | {'ALL'} | ({'A100-foreign'} if active else set())
    require(set(report['physical']) == expected_keys, 'Physical metric pool set')
    for key, entry in report['physical'].items():
        sub = frame if key == 'ALL' else frame[frame.partition == key]
        pool = nodes if key == 'ALL' else nodes[nodes.node_name.isin(donor)] if key == 'A100-foreign' else nodes[(nodes.gpu_model == key) & ~nodes.node_name.isin(donor)]
        g = c = full_g = full_c = 0
        for row in sub.itertuples():
            overlap = max(0, min(row.finish, h)-row.start)
            g += overlap*row.worker_num*row.gpu_request
            c += overlap*row.worker_num*row.cpu_request
            full_g += row.duration*row.worker_num*row.gpu_request
            full_c += row.duration*row.worker_num*row.cpu_request
        expected = {'nodes': len(pool), 'gpus': pool.gpu_capacity_num.sum(), 'cpus': pool.cpu_num.sum(),
                    'gpu_allocation_rate_at_horizon': g/(h*pool.gpu_capacity_num.sum()),
                    'cpu_allocation_rate_at_horizon': c/(h*pool.cpu_num.sum()),
                    'full_gpu_hours': full_g/3600, 'full_cpu_hours': full_c/3600,
                    'window_idle_gpu_hours': (h*pool.gpu_capacity_num.sum()-g)/3600}
        for name, value in expected.items():
            close(entry[name], value, key+name)
        if not sub.empty:
            shared = entry['shared_evaluator']
            # Check all shared evaluator fields, too.
            wait = sub.start-sub.submit_time
            slowdown = np.maximum(1., (sub.finish-sub.submit_time)/np.maximum(sub.duration, 60))
            expected_shared = {'jobs': len(sub), 'mean_wait_hours': wait.mean()/3600,
                               'median_wait_hours': wait.quantile(.5)/3600, 'p95_wait_hours': wait.quantile(.95)/3600,
                               'p99_wait_hours': wait.quantile(.99)/3600, 'max_wait_hours': wait.max()/3600,
                               'mean_jct_hours': (sub.finish-sub.submit_time).mean()/3600,
                               'zero_wait_fraction': (wait == 0).mean(), 'mean_bounded_slowdown_60s': slowdown.mean(),
                               'p99_bounded_slowdown_60s': np.quantile(slowdown, .99),
                               'completed_at_horizon': (sub.finish <= h).sum(),
                               'gpu_allocation_rate_at_horizon': expected['gpu_allocation_rate_at_horizon'],
                               'cpu_allocation_rate_at_horizon': expected['cpu_allocation_rate_at_horizon'],
                               'final_completion_days': sub.finish.max()/86400}
            require(set(shared) == set(expected_shared), 'Shared metric keys')
            for name, value in expected_shared.items():
                close(shared[name], value, key+name)
    close(report['makespan_days'], frame.finish.max()/86400, 'makespan')
    require(report['routing']['counts'] == frame.route_reason.value_counts().to_dict(), 'Routing counts')
    a = frame[masks['original_A10']]; r = frame[masks['routed_A10']]
    work = lambda f: sum(x.original_duration*x.worker_num*x.gpu_request for x in f.itertuples())
    close(report['routing']['original_A10_gpu_work_fraction_routed'], work(r)/work(a) if len(a) else 0, 'Routed GPU work')
    return {'status': 'PASS', 'method': 'independent aggregation from persisted job records and physical capacities'}


def verify_comparison(b, t, horizon, report):
    b = b.set_index('job_name').sort_index(); t = t.set_index('job_name').sort_index()
    require(b.index.equals(t.index), 'Pair IDs')
    for key, model in [('original_A10', 'A10'), ('native_A100', 'A100-SXM4-80GB'), ('ALL', None)]:
        x = b if model is None else b[b.original_gpu_model == model]
        y = t.loc[x.index]
        dw = y.start-x.start; de = y.finish-x.finish
        expected = {'jobs': len(x), 'mean_delta_wait_hours': dw.sum()/len(x)/3600,
                    'mean_delta_jct_hours': de.sum()/len(x)/3600,
                    'positive_extra_wait_hours': sum(v for v in dw if v > 0)/3600,
                    'p99_delta_wait_hours': dw.quantile(.99)/3600, 'max_delta_wait_hours': dw.max()/3600,
                    'baseline_zero_new_delay_jobs': sum((x.start == x.submit_time) & (y.start > y.submit_time)),
                    'later_completion_jobs': sum(de > 0), 'earlier_completion_jobs': sum(de < 0), 'equal_completion_jobs': sum(de == 0),
                    'positive_completion_delay_hours': sum(v for v in de if v > 0)/3600,
                    'completion_count_delta_at_horizon': sum(y.finish <= horizon)-sum(x.finish <= horizon)}
        require(set(report[key]) == set(expected), 'Pair metric keys')
        for name, value in expected.items():
            require(math.isclose(float(report[key][name]), float(value), rel_tol=1e-11, abs_tol=1e-10), 'Paired metric '+name)
    return {'status': 'PASS', 'method': 'original job ID pairing'}
