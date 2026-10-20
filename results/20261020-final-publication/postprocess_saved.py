#!/usr/bin/env python3
"""Read saved job timings only: no scheduler import, execution or ledger replay."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FORMAL = ROOT / 'results/20261019-b-v2-integration-candidate/v2_runtime_equivalence.json'
PAIRED = ROOT / 'results/20261018-b-q3-v2-r1-6f2c8a10/paired.csv'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime', type=Path, default=ROOT/'outputs/v2-integration-runtime-20261019')
    p.add_argument('--out', type=Path, default=Path(__file__).with_name('saved_timing_checks.json'))
    a = p.parse_args()
    formal = {r['case']:r for r in json.loads(FORMAL.read_text())['cases']}
    historical = list(csv.DictReader(PAIRED.open()))
    base = pd.read_csv(a.runtime/'C0/jobs.csv.gz').set_index('job_name').sort_index()
    original = pd.read_csv(a.runtime/'B2/jobs.csv.gz').set_index('job_name').sort_index()
    fields = ['submit_time','original_duration','worker_num','gpu_request','cpu_units','start','finish']
    equivalence = {}
    for model in ['A10','A100-SXM4-80GB']:
        ids = base.index[base.original_gpu_model == model]
        pd.testing.assert_frame_equal(base.loc[ids,fields], original.loc[ids,fields], check_exact=True)
        equivalence[model] = {'jobs':len(ids), 'fields':fields, 'equal':True,
          'canonical_sha256':hashlib.sha256(base.loc[ids,fields].to_csv().encode()).hexdigest()}
    records = []
    for case in ['C0','C1','C2','C3','C4']:
        path = a.runtime/case/'jobs.csv.gz'
        assert sha(path) == formal[case]['jobs_sha256']
        frame = pd.read_csv(path).set_index('job_name').sort_index()
        assert frame.index.equals(base.index)
        ids_a = base.index[base.original_gpu_model=='A10']
        ids_n = base.index[base.original_gpu_model=='A100-SXM4-80GB']
        harm_a = int((frame.loc[ids_a,'finish'] > base.loc[ids_a,'finish']).sum())
        dw = (frame.loc[ids_n,'start']-frame.loc[ids_n,'submit_time'])-(base.loc[ids_n,'start']-base.loc[ids_n,'submit_time'])
        harm_n = int((dw>0).sum())
        route = {'C0':'M0','C1':'R0','C2':'R0','C3':'R-shape','C4':'R-shape'}[case]
        sigma = formal[case]['config']['sigma']
        matched = [r for r in historical if r['policy']=='SJF-HOL' and r['option']==route and r['reference']=='M0' and (case=='C0' or float(r['sigma'])==sigma)]
        ha = next(r for r in matched if r['cohort']=='A10')
        hn = next(r for r in matched if r['cohort']=='native_A100')
        assert harm_a==int(ha['harmed_jobs']) and harm_n==int(hn['wait_harmed_jobs'])
        allocation = {}
        if case!='C0':
            total = 0
            for partition,capacity in [('A100-SXM4-80GB',2976),('A100-foreign',480)]:
                sub=frame[frame.partition==partition]
                overlap=(sub.finish.clip(upper=7776000)-sub.start).clip(lower=0)
                gpu_seconds=int((overlap*sub.worker_num*sub.gpu_request).sum())
                rate=gpu_seconds/(capacity*7776000)
                expected=formal[case]['metrics']['physical'][partition]['gpu_allocation_rate_at_horizon']
                assert abs(rate-expected)<1e-14
                allocation[partition]={'capacity':capacity,'window_gpu_seconds':gpu_seconds,'own_rate':rate,'full_pool_contribution':gpu_seconds/(3456*7776000),'source_field':'sum(max(0,min(finish,H)-start)*worker_num*gpu_request)'}
                total+=gpu_seconds
            allocation['full_pool_rate']=total/(3456*7776000)
            weighted=(2976*allocation['A100-SXM4-80GB']['own_rate']+480*allocation['A100-foreign']['own_rate'])/3456
            assert abs(weighted-allocation['full_pool_rate'])<1e-14
        records.append({'case':case,'source':f'outputs/v2-integration-runtime-20261019/{case}/jobs.csv.gz','sha256':sha(path),'baseline':'C0','baseline_sha256':sha(a.runtime/'C0/jobs.csv.gz'),'a10_later_finish_count':harm_a,'native_a100_wait_increase_count':harm_n,'historical_pair_match':True,'historical_pair_source':str(PAIRED.relative_to(ROOT)),'historical_selector':{'policy':'SJF-HOL','option':route,'sigma':None if case=='C0' else sigma,'reference':'M0'},'allocation':allocation})
    report={'scope':'Read-only timing postprocessing; zero scheduler calls; zero ledger replay','C0_B2_cohort_equality':equivalence,'historical_M0_bridge':'Formal integration records verify B2 against M0 and C0 against the same non-GS1 reference. The added exact per-ID C0/B2 comparison is restricted to A10 and native A100; no full-cluster equivalence claimed.','B2_sha256':sha(a.runtime/'B2/jobs.csv.gz'),'formal_source':str(FORMAL.relative_to(ROOT)),'formal_source_sha256':sha(FORMAL),'records':records}
    a.out.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: five saved schedules; exact cohort bridge, paired harm, integer GPU-second allocation')

if __name__=='__main__': main()
