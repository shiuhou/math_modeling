"""Small deterministic checks retained from the supplied research tool."""
import unittest
import numpy as np
import pandas as pd
from gpu_scheduling.placement import slots
from gpu_scheduling.simulator import simulate_pool
from gpu_scheduling.validation import reference_small

def tests() -> list[str]:
    nd=pd.DataFrame(dict(node_name=[0,1],gpu_model=['X','X'],gpu_capacity_num=[1,1],cpu_num=[4,4],cpu_units=[400,400]))
    j=pd.DataFrame(dict(job_name=[0,1,2],gpu_model=['X']*3,gpu_request=[1,1,1],cpu_request=[4.,4.,4.],
            cpu_units=[400]*3,worker_num=[1,2,1],submit_time=[0,1,2],duration=[10,5,3]))
    fc=simulate_pool(nd,j,'FCFS');sj=simulate_pool(nd,j,'SJF-HOL')
    assert fc['starts'].tolist()==[0,10,15]
    assert sj['starts'].tolist()==[0,10,2]
    assert slots(np.array([1,1]),np.array([400,400]),2,400).sum()==0 # worker cannot span nodes
    assert slots(np.array([1,1]),np.array([0,0]),1,0).sum()==2 # zero CPU demand
    # Exact fractional CPU, co-location, resource release and same-time arrival.
    nd2=pd.DataFrame(dict(node_name=[0],gpu_model=['X'],gpu_capacity_num=[4],cpu_num=[1],cpu_units=[100]))
    j2=pd.DataFrame(dict(job_name=[0,1,2],gpu_model=['X']*3,gpu_request=[1,1,1],cpu_request=[.6,.6,.4],
             cpu_units=[60,60,40],worker_num=[1,1,1],submit_time=[0,0,2],duration=[2,2,2]))
    assert simulate_pool(nd2,j2,'FCFS')['starts'].tolist()==[0,2,2]
    # Deterministic tie-break at arrival zero: ascending job_name.
    assert simulate_pool(nd2,j2.iloc[[1,0,2]],'FCFS')['starts'].tolist()==[0,2,2]
    rng=np.random.default_rng(20261014)
    for trial in range(30):
        nd3=pd.DataFrame({'node_name':[0,1,2],'gpu_model':['X']*3,
             'gpu_capacity_num':rng.integers(1,5,3),'cpu_num':rng.integers(1,5,3)})
        nd3['cpu_units']=nd3.cpu_num*100
        rows=[]
        for jid in range(15):
            while True:
                q=int(rng.integers(1,5));c=int(rng.choice([0,20,60,100,150,200,400]));w=int(rng.integers(1,4))
                if slots(nd3.gpu_capacity_num.to_numpy(),nd3.cpu_units.to_numpy(),q,c).sum()>=w:break
            rows.append(dict(job_name=jid,gpu_model='X',gpu_request=q,cpu_request=c/100,cpu_units=c,
                worker_num=w,submit_time=int(rng.integers(0,12)),duration=int(rng.integers(1,9))))
        jj=pd.DataFrame(rows)
        for pol in ('FCFS','SJF-HOL'):
            assert simulate_pool(nd3,jj,pol)['starts'].tolist()==reference_small(nd3,jj,pol)
    return ['30 seeded small instances x two policies match independent scalar time-step reference PASS',
            'FCFS hand-calculated timing PASS','SJF-HOL hand-calculated timing PASS',
            'gang all-or-nothing and node-local worker demand PASS','zero CPU demand PASS',
            'fractional CPU, same-time release/arrival, co-location PASS','deterministic tie-break PASS']



class SuppliedBaselineTests(unittest.TestCase):
    def test_supplied_hand_cases_and_scalar_oracle(self):
        tests()
