"""Replay the review-base module in memory; no second active scheduler."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'problems/2026_gpu_scheduling/src'))
sys.path.insert(0, str(ROOT / 'problems/2026_gpu_scheduling/tests'))
from gpu_scheduling.data import read_data, native
from gpu_scheduling.evaluation import metrics
from gpu_scheduling.simulator import simulate_pool
from gpu_scheduling.validation import validate_reservations
from test_q2_m1 import nodes, jobs

BASE = '0add5f1b56caad43048c93b38218b7f0bb1bfe84'
def review_module(name):
    path = f'problems/2026_gpu_scheduling/src/gpu_scheduling/{name}.py'
    source = subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT)
    mod = types.ModuleType(f'gpu_scheduling.review_{name}')
    mod.__package__ = 'gpu_scheduling'
    exec(compile(source, f'{BASE}:{path}', 'exec'), mod.__dict__)
    return mod
old = review_module('simulator')
old_validator = review_module('validation')
nd = nodes((1, 1), (8, 8))
jj = jobs([0, 1, 2], [10, 1, 2], workers=[1, 2, 1], submits=[0, 1, 1])
probes = {}
for label, simulate in [('before', old.simulate_pool), ('after', simulate_pool)]:
    young = simulate(nd, jj, 'SPT-URGENT-HOL', theta_seconds=100,
                     event_mode='arrival-completion-only')
    probes[label] = {'young_starts':young['starts'].tolist()}
    aged = jobs([0, 1, 2, 3], [20, 5, 1, 1], workers=[1, 2, 2, 1], submits=[0, 1, 2, 7])
    for mode in ('shared-timer', 'arrival-completion-only'):
        r = simulate(nd, aged, 'SPT-URGENT-HOL', theta_seconds=4, event_mode=mode)
        probes[label][mode] = {k:r['reservations'][0][k] for k in ('protected_job_name','issued_time','promised_R','fulfillment')}
r = simulate_pool(nd, jj, 'EASY-TIME')
bad = copy.deepcopy(r); bad['reservations'] = None
old_validator.validate_reservations(nd, bad['jobs'], bad)
probes['before']['null_evidence'] = 'INCORRECTLY_ACCEPTED'
try:
    validate_reservations(nd, bad['jobs'], bad)
except AssertionError:
    probes['after']['null_evidence'] = 'REJECTED'
else:
    raise AssertionError('null accepted')
# Preserve the actual small allocation and promise evidence without raw data.
synthetic = {'nodes':nd.to_dict('records'), 'jobs':r['jobs'].to_dict('records'),
             **{k:r[k] for k in ('starts','ends','plans','reservations','events')}}
(Path(__file__).parent / 'synthetic-evidence.json').write_text(json.dumps(native(synthetic),indent=2)+'\n')
nodes_raw,jobs_raw,hashes = read_data(ROOT / 'problems/2026_gpu_scheduling/data/raw')
checks=[]
for mode in ('shared-timer', 'arrival-completion-only'):
    for policy in ('FCFS-HOL','SPT-HOL'):
        for model, frame in jobs_raw.groupby('gpu_model', sort=True):
            frame=frame.head(64)
            pool=nodes_raw[nodes_raw.gpu_model==model]
            a=old.simulate_pool(pool,frame,policy,theta_seconds=4,event_mode=mode)
            b=simulate_pool(pool,frame,policy,theta_seconds=4,event_mode=mode)
            for key in ('starts','ends'):
                assert a[key].tolist()==b[key].tolist()
            for key in ('plans','events','reservations'):
                assert a[key]==b[key]
            for horizon in (7776000,7775878):
                assert metrics(a,pool,horizon)==metrics(b,pool,horizon)
            digest=hashlib.sha256(json.dumps(native({k:b[k] for k in ('starts','ends','plans')}),sort_keys=True).encode()).hexdigest()
            checks.append({'mode':mode,'policy':policy,'pool':str(model),'jobs':len(frame),
                           'status':'PASS','schedule_sha256':digest})
output={'base':BASE,'data_sha256':hashes,'probes':probes,'baseline_regression':checks,
        'baseline_scope':'first 64 jobs per pool; both modes; timings, placements, events, reservations and metrics at both horizons',
        'full_trace_rerun':'NOT_RUN; fix is gated to urgent policies, baseline branches unchanged'}
(Path(__file__).parent / 'regression.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(probes,indent=2)); print(f'PASS: {len(checks)} baseline pool comparisons')
