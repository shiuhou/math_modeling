"""Independent node-ledger and reservation replay plus a small scalar oracle."""
import numpy as np
import pandas as pd
from .placement import check_plan, slots

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


def validate_reservations(nodes: pd.DataFrame, jobs: pd.DataFrame, result: dict) -> None:
    """Replay M1 promise certificates independently of scheduler decisions.

    This validator reconstructs the free vectors at issuance and at the
    original immutable ``R`` from the persisted allocations.  It does not call
    a scheduler ``safe`` predicate and therefore catches stale or self-
    reported certificates.
    """
    for field in ("reservations", "events"):
        if not isinstance(result.get(field), list) or any(
                not isinstance(item, dict) for item in result[field]):
            raise AssertionError(f"reservation replay requires explicit {field} list of records")
    reservations = result["reservations"]
    starts = np.asarray(result["starts"], dtype=np.int64)
    ends = np.asarray(result["ends"], dtype=np.int64)
    plans = result["plans"]
    if len(starts) != len(jobs) or len(plans) != len(jobs):
        raise AssertionError("reservation replay requires a complete schedule")
    caps_g = nodes.gpu_capacity_num.to_numpy(dtype=np.int64)
    caps_c = nodes.cpu_units.to_numpy(dtype=np.int64)
    ids = {int(x): i for i, x in enumerate(jobs.job_name)}
    events = result["events"]
    if reservations and not events:
        raise AssertionError("reservation replay requires persisted event order")
    issued_items = [item for item in events if item.get("kind") == "reservation_issued"]
    fulfilled_items = [item for item in events if item.get("kind") == "reservation_fulfilled"]
    issued_by_id = {item.get("promise_id"): item for item in issued_items}
    fulfilled_by_id = {item.get("promise_id"): item for item in fulfilled_items}
    recorded_ids = {item.get("promise_id") for item in reservations}
    if (len(issued_items) != len(issued_by_id) or len(fulfilled_items) != len(fulfilled_by_id)
            or set(issued_by_id) != recorded_ids or set(fulfilled_by_id) != recorded_ids):
        raise AssertionError("reservation evidence is missing or has an unrecorded promise")
    seen_promises = set()
    for promise in reservations:
        pid = promise.get("promise_id")
        if not pid or pid in seen_promises:
            raise AssertionError("duplicate or missing promise_id")
        seen_promises.add(pid)
        protected_name = int(promise["protected_job_name"])
        if protected_name not in ids:
            raise AssertionError("unknown protected job")
        protected = ids[protected_name]
        issued = int(promise["issued_time"])
        promised_r = int(promise["promised_R"])
        issued_event = issued_by_id[pid]
        if (int(issued_event.get("time")) != issued
                or int(issued_event.get("protected_job")) != int(promise["protected_job"])
                or int(issued_event.get("promised_R")) != promised_r):
            raise AssertionError("reservation issuance does not match its promise record")
        fulfilled_event = fulfilled_by_id[pid]
        if (int(fulfilled_event.get("protected_job")) != int(promise["protected_job"])
                or int(fulfilled_event.get("promised_R")) != promised_r):
            raise AssertionError("reservation fulfillment does not match its promise record")
        if promised_r < issued or starts[protected] < 0 or starts[protected] > promised_r:
            raise AssertionError("promise timing contract")
        q = int(jobs.gpu_request.iloc[protected])
        c = int(jobs.cpu_units.iloc[protected])
        w = int(jobs.worker_num.iloc[protected])

        current_g, current_c = caps_g.copy(), caps_c.copy()
        issued_events = [idx for idx, item in enumerate(events)
                         if item.get("kind") == "reservation_issued" and item.get("promise_id") == pid]
        if len(issued_events) != 1 or int(events[issued_events[0]]["time"]) != issued:
            raise AssertionError("missing or duplicate promise event")
        for item in events[:issued_events[0]]:
            if item.get("kind") not in ("start", "finish"):
                continue
            j = int(item["job"])
            if j < 0 or j >= len(jobs) or int(item["time"]) != int(starts[j] if item["kind"] == "start" else ends[j]):
                raise AssertionError("event disagrees with timing ledger")
            sign = -1 if item["kind"] == "start" else 1
            for node, count in plans[j]:
                current_g[int(node)] += sign * int(count) * int(jobs.gpu_request.iloc[j])
                current_c[int(node)] += sign * int(count) * int(jobs.cpu_units.iloc[j])
        if np.any(current_g < 0) or np.any(current_c < 0):
            raise AssertionError("negative current snapshot")
        recorded_current = promise.get("current_free_initial", {})
        if current_g.tolist() != list(recorded_current.get("gpu", [])) or current_c.tolist() != list(recorded_current.get("cpu", [])):
            raise AssertionError("current snapshot does not replay from event order")

        # At R the full pool capacity is restored, then only allocations that
        # cross R remain occupied.  Starting from current_free and subtracting
        # crossing work would double-count jobs already present at issuance.
        future_g, future_c = caps_g.copy(), caps_c.copy()
        active_at_issue = set()
        for item in events[:issued_events[0]]:
            if item.get("kind") == "start":
                active_at_issue.add(int(item["job"]))
            elif item.get("kind") == "finish":
                active_at_issue.discard(int(item["job"]))
        for j in active_at_issue:
            if ends[j] > promised_r:
                for node, count in plans[j]:
                    future_g[int(node)] -= int(count) * int(jobs.gpu_request.iloc[j])
                    future_c[int(node)] -= int(count) * int(jobs.cpu_units.iloc[j])
        accepted = {int(x) for x in promise.get("accepted_backfill_ids", [])}
        if len(accepted) != len(promise.get("accepted_backfill_ids", [])):
            raise AssertionError("duplicate accepted backfill id")
        policy = str(result.get("policy", promise.get("policy", "")))
        crossing_allowed = {"SPT-URGENT-FIXED", "SPT-URGENT-FLEX", "EASY-NR"}
        for j in range(len(jobs)):
            if j == protected or not (issued <= starts[j] < promised_r) or j in active_at_issue:
                continue
            if ends[j] > promised_r and policy not in crossing_allowed:
                raise AssertionError("backfill crosses immutable promised R")
            if j not in accepted:
                raise AssertionError("post-issuance backfill missing from certificate")
        for j in accepted:
            if j < 0 or j >= len(jobs) or j == protected or starts[j] < issued or j in active_at_issue:
                raise AssertionError("invalid accepted backfill id")
        recorded = promise.get("future_free_initial", {})
        if future_g.tolist() != list(recorded.get("gpu", [])) or future_c.tolist() != list(recorded.get("cpu", [])):
            raise AssertionError("future snapshot does not replay from allocations")
        # Replay each sparse crossing certificate in event order.  The
        # current resource state is reconstructed from prior start/finish
        # events; only the future vector and head witness are stored as deltas.
        crossing_events = [item for item in events
                           if item.get("kind") == "certificate_update"
                           and item.get("promise_id") == pid]
        recorded_updates = [item for item in promise.get("certificate_updates", []) if "job" in item]
        if len(crossing_events) != len(recorded_updates):
            raise AssertionError("certificate update evidence is incomplete")
        if {int(item.get("job")) for item in crossing_events} != {j for j in accepted if ends[j] > promised_r}:
            raise AssertionError("crossing backfill certificate ids do not match allocations")
        witness = tuple((int(node), int(count)) for node, count in promise.get("placement_witness", []))
        previous_version = int(promise["state_version"])
        # The recorded state_version is the final certificate version.  Each
        # update carries its own predecessor, so replay starts at issuance.
        initial_version = int(issued_event.get("state_version", promise.get("state_version", 0)))
        previous_version = initial_version
        for item, recorded_update in zip(crossing_events, recorded_updates):
            for key in ("time", "job", "state_version", "previous_state_version", "planner",
                        "plan", "future_free_at_R", "head_witness"):
                if item.get(key) != recorded_update.get(key):
                    raise AssertionError("certificate event and record differ")
            j = int(item["job"])
            if policy not in crossing_allowed:
                raise AssertionError("TIME reservation contains a crossing certificate")
            plan = tuple((int(node), int(count)) for node, count in plans[j])
            if tuple(tuple(x) for x in item.get("plan", [])) != plan:
                raise AssertionError("certificate plan differs from allocation ledger")
            if int(item.get("time")) != int(starts[j]) or int(ends[j]) <= promised_r:
                raise AssertionError("invalid crossing certificate timing")
            version = int(item.get("state_version"))
            if int(item.get("previous_state_version")) != previous_version or version <= previous_version:
                raise AssertionError("certificate version chain is broken")
            current_before_g, current_before_c = caps_g.copy(), caps_c.copy()
            event_index = events.index(item)
            for prior in events[:event_index]:
                if prior.get("kind") not in ("start", "finish"):
                    continue
                k = int(prior["job"])
                if int(prior["time"]) != int(starts[k] if prior["kind"] == "start" else ends[k]):
                    raise AssertionError("event disagrees with timing ledger")
                sign = -1 if prior["kind"] == "start" else 1
                for node, count in plans[k]:
                    current_before_g[int(node)] += sign * int(count) * int(jobs.gpu_request.iloc[k])
                    current_before_c[int(node)] += sign * int(count) * int(jobs.cpu_units.iloc[k])
            check_plan(current_before_g, current_before_c, int(jobs.gpu_request.iloc[j]),
                       int(jobs.cpu_units.iloc[j]), plan, int(jobs.worker_num.iloc[j]))
            old_future_g, old_future_c = future_g.copy(), future_c.copy()
            delta_g = np.zeros_like(future_g); delta_c = np.zeros_like(future_c)
            for node, count in plan:
                delta_g[node] += count * int(jobs.gpu_request.iloc[j])
                delta_c[node] += count * int(jobs.cpu_units.iloc[j])
            future_g, future_c = future_g - delta_g, future_c - delta_c
            if np.any(future_g < 0) or np.any(future_c < 0):
                raise AssertionError("certificate future snapshot is negative")
            mode = str(item.get("planner"))
            if mode == "fixed":
                z_g = np.zeros_like(future_g); z_c = np.zeros_like(future_c)
                for node, count in witness:
                    z_g[node] += count * q; z_c[node] += count * c
                effective_g = np.minimum(current_before_g, old_future_g - z_g)
                effective_c = np.minimum(current_before_c, old_future_c - z_c)
                check_plan(effective_g, effective_c, int(jobs.gpu_request.iloc[j]),
                           int(jobs.cpu_units.iloc[j]), plan, int(jobs.worker_num.iloc[j]))
            elif mode == "flex":
                head_witness = tuple((int(node), int(count)) for node, count in item.get("head_witness", []))
                check_plan(future_g, future_c, q, c, head_witness, w)
                if int(slots(future_g, future_c, q, c).sum()) < w:
                    raise AssertionError("FLEX certificate loses protected head slots")
                witness = head_witness
            else:
                raise AssertionError("unknown crossing planner certificate")
            recorded_future = item.get("future_free_at_R", {})
            if future_g.tolist() != list(recorded_future.get("gpu", [])) or future_c.tolist() != list(recorded_future.get("cpu", [])):
                raise AssertionError("certificate future delta does not replay")
            previous_version = version
        recorded_at_r = promise.get("future_free_at_R", {})
        if future_g.tolist() != list(recorded_at_r.get("gpu", [])) or future_c.tolist() != list(recorded_at_r.get("cpu", [])):
            raise AssertionError("future snapshot was changed without a certificate update")
        final_witness = tuple((int(node), int(count)) for node, count in promise.get("placement_witness", []))
        check_plan(future_g, future_c, q, c, final_witness, w)
        if int(slots(future_g, future_c, q, c).sum()) < w:
            raise AssertionError("future snapshot does not contain protected gang")
        fulfillment = promise.get("fulfillment", {})
        if fulfillment.get("status") != "FULFILLED" or int(fulfillment.get("time")) != int(starts[protected]):
            raise AssertionError("missing or inconsistent fulfillment record")
        if int(fulfilled_event.get("time")) != int(fulfillment.get("time")):
            raise AssertionError("fulfillment event time does not match its promise record")
        fulfillment_updates = [item for item in promise.get("certificate_updates", []) if item.get("event") == "fulfillment"]
        if len(fulfillment_updates) != 1 or int(fulfillment_updates[0].get("time")) != int(fulfillment.get("time")):
            raise AssertionError("fulfillment certificate update is missing")
        if int(fulfilled_event.get("state_version")) != int(fulfillment_updates[0].get("state_version")):
            raise AssertionError("fulfillment certificate version differs from event")



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
