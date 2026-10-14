#!/usr/bin/env python3
"""Recheck persisted baseline inputs, metrics and per-node placement feasibility."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
PROBLEM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROBLEM / 'src'))
import pandas as pd
from gpu_scheduling.data import prepare_data, read_data
from gpu_scheduling.evaluation import metrics
from gpu_scheduling.validation import validate, validate_reservations
from verify_intake import compare_inputs


def verify(source, run):
    nodes, jobs, hashes = read_data(source)
    record = json.loads((run/'run.json').read_text())
    if hashes != record['data_sha256']: raise ValueError('Input byte hashes differ')
    if record['configuration']['audit_only']: raise ValueError('Audit-only run has no schedule to validate')
    for name, expected in record['outputs'].items():
        if hashlib.sha256((run/name).read_bytes()).hexdigest() != expected: raise ValueError(f'Output hash mismatch: {name}')
    if record['scope'] == 'smoke_first_64_per_model': jobs = jobs.groupby('gpu_model', sort=False).head(64)
    saved_metrics = json.loads((run/'baseline_metrics.json').read_text())
    horizon = record['configuration']['horizon_seconds']
    checked = []
    for policy in record['configuration']['policies']:
        frame = pd.read_csv(run/f'{policy}_job_times.csv.gz')
        compare_inputs(jobs, frame)
        _, frame = prepare_data(nodes, frame)
        placement = pd.read_csv(run/f'{policy}_node_placements.csv.gz')
        if placement.isna().any().any() or set(placement.job_name) != set(frame.job_name):
            raise ValueError('Incomplete placement job IDs')
        if not set(placement.node_name) <= set(nodes.node_name): raise ValueError('Unknown placement node')
        lookup = {int(j): i for i,j in enumerate(frame.job_name)}
        node_lookup = {int(n): i for i,n in enumerate(nodes.node_name)}
        plans = [[] for _ in range(len(frame))]
        for jid, nid, workers in placement.itertuples(index=False, name=None):
            if workers != int(workers) or workers <= 0: raise ValueError('Invalid worker count')
            plans[lookup[jid]].append((node_lookup[nid], int(workers)))
        validate(nodes, frame, frame.start.to_numpy(), frame.finish.to_numpy(), plans)
        reservation_checks = []
        reservation_files = sorted(run.glob(f'{policy}_*_reservations.json'))
        for evidence in reservation_files:
            payload = json.loads(evidence.read_text())
            model = payload['gpu_model']
            sub = frame[frame.gpu_model == model].reset_index(drop=True)
            pool = nodes[nodes.gpu_model == model].reset_index(drop=True)
            sub_lookup = {int(j): i for i, j in enumerate(sub.job_name)}
            sub_node_lookup = {int(n): i for i, n in enumerate(pool.node_name)}
            sub_plans = [[] for _ in range(len(sub))]
            for jid, nid, workers in placement[placement.job_name.isin(sub.job_name)].itertuples(index=False, name=None):
                sub_plans[sub_lookup[int(jid)]].append((sub_node_lookup[int(nid)], int(workers)))
            validate_reservations(pool, sub, {
                'starts': sub.start.to_numpy(),
                'ends': sub.finish.to_numpy(),
                'plans': sub_plans,
                'reservations': payload.get('reservations', []),
                'events': payload.get('events', []),
            })
            reservation_checks.append({'gpu_model': model, 'status': 'PASS', 'reservations': len(payload.get('reservations', []))})
        rows = [row for row in saved_metrics if row['policy'] == policy]
        expected_models = set(frame.gpu_model) | {'ALL'}
        if {row['gpu_model'] for row in rows} != expected_models or len(rows) != len(expected_models):
            raise ValueError('Missing/duplicate metric pool rows')
        for row in rows:
            model = row['gpu_model']
            sub = frame if model == 'ALL' else frame[frame.gpu_model == model]
            pool = nodes if model == 'ALL' else nodes[nodes.gpu_model == model]
            measured = metrics({'jobs':sub,'starts':sub.start.to_numpy(),'ends':sub.finish.to_numpy()}, pool, horizon)
            if set(row) != set(measured) | {'policy','gpu_model'}:raise ValueError('Metric keys differ')
            for name,value in measured.items():
                if not math.isclose(value, row[name], rel_tol=1e-11, abs_tol=1e-10): raise ValueError(f'{policy}/{model}/{name} mismatch')
        checked.append({'policy':policy,'jobs':len(frame),'ledger_rows':len(placement),'input_fields':'PASS','capacity_replay':'PASS','reservation_replay': reservation_checks or 'NOT_APPLICABLE','metrics':'PASS'})
    return {'status':'PASS','scope':record['scope'],'checks':checked,'run_sha256':hashlib.sha256((run/'run.json').read_bytes()).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=PROBLEM/'data/raw')
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():parser.error('Output exists; choose a new file')
    result=verify(args.data,args.run)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print('PASS: persisted input fields, timing, per-node CPU/GPU ledger and all metrics')


if __name__=='__main__':main()
