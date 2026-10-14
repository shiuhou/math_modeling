"""Independent node-ledger replay and a small scalar time-step oracle."""
import numpy as np
import pandas as pd

def validate(nodes: pd.DataFrame,jobs: pd.DataFrame,s: np.ndarray,e: np.ndarray,plans: list) -> None:
    """Independent node-by-node event replay from the final allocation ledger."""
    if len(s)!=len(jobs) or len(e)!=len(jobs) or len(plans)!=len(jobs):
        raise AssertionError('Incomplete timing or placement ledger')
    if not np.all(s>=jobs.submit_time.to_numpy()) or not np.all(e-s==jobs.duration.to_numpy()):
        raise AssertionError('Timing contract')
    ledgers=[[] for _ in range(len(nodes))]
    cols=jobs[['gpu_request','cpu_units','worker_num','gpu_model']]
    for j,(q,c,w,g) in enumerate(cols.itertuples(index=False,name=None)):
        if sum(n for _,n in plans[j])!=w:raise AssertionError('Worker count')
        for m,n in plans[j]:
            if not isinstance(m,(int,np.integer)) or not isinstance(n,(int,np.integer)) or not 0<=m<len(nodes) or n<=0 or nodes.gpu_model.iloc[m]!=g:raise AssertionError('Placement contract')
            ledgers[m].append((int(s[j]),1,n*q,n*c))
            ledgers[m].append((int(e[j]),0,-n*q,-n*c))
    for m,ledger in enumerate(ledgers):
        gu=cu=0
        for _,_,dg,dc in sorted(ledger):
            gu+=dg;cu+=dc
            if not(0<=gu<=int(nodes.gpu_capacity_num.iloc[m]) and 0<=cu<=int(nodes.cpu_units.iloc[m])):
                raise AssertionError(f'Independent capacity replay failed: node {m}')
        if gu!=0 or cu!=0:raise AssertionError('Final allocation is not zero')



def reference_small(nodes: pd.DataFrame, jobs: pd.DataFrame, policy: str) -> list[int]:
    """Slow integer-time reference for small test fixtures; deliberately no NumPy placement."""
    jobs=jobs.sort_values(['submit_time','job_name'],kind='stable').reset_index(drop=True)
    rows=list(jobs.itertuples(index=False)); caps=[(int(x.gpu_capacity_num),int(x.cpu_units)) for x in nodes.itertuples()]
    free=[list(x) for x in caps]; pending=[];active={};started=[-1]*len(rows)
    limit=int(jobs.submit_time.max()+jobs.duration.sum()+1)
    for t in range(limit+1):
        for k in list(active):
            end,plan=active[k]
            if end==t:
                for m,w in plan:free[m][0]+=w*int(rows[k].gpu_request);free[m][1]+=w*int(rows[k].cpu_units)
                del active[k]
        pending.extend(k for k,j in enumerate(rows) if j.submit_time==t)
        key=(lambda k:(rows[k].submit_time,rows[k].job_name)) if policy=='FCFS' else (lambda k:(rows[k].duration,rows[k].submit_time,rows[k].job_name))
        pending.sort(key=key)
        while pending:
            k=pending[0];j=rows[k];todo=int(j.worker_num);plan=[]
            for m,(g,c) in enumerate(free):
                room=g//int(j.gpu_request)
                if j.cpu_units:room=min(room,c//int(j.cpu_units))
                take=min(todo,room)
                if take:plan.append((m,take));todo-=take
                if not todo:break
            if todo:break
            for m,w in plan:free[m][0]-=w*int(j.gpu_request);free[m][1]-=w*int(j.cpu_units)
            started[k]=t;active[k]=(t+int(j.duration),plan);pending.pop(0)
        if all(x>=0 for x in started) and not active:return started
    raise AssertionError('Reference simulation did not finish')
