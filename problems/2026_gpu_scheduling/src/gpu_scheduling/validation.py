"""Independent node-ledger and reservation replay plus a small scalar oracle."""
import hashlib
import json
import numpy as np
import pandas as pd
from .placement import check_plan, slots


def _snapshot_hash(gpu, cpu) -> str:
    payload = {"gpu": [int(x) for x in gpu], "cpu": [int(x) for x in cpu]}
    return hashlib.sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).hexdigest()

def validate(nodes: pd.DataFrame, jobs: pd.DataFrame, s: np.ndarray, e: np.ndarray, plans: list) -> None:
    """Independent atomic gang replay; completions precede starts at ties."""
    if len(s) != len(jobs) or len(e) != len(jobs) or len(plans) != len(jobs):
        raise AssertionError('Incomplete timing or placement ledger')
    for values in (s, e):
        if any(isinstance(x, (bool, np.bool_)) or not isinstance(x, (int, np.integer)) for x in values):
            raise AssertionError('Integer timing required')
    if not (jobs.duration > 0).all() or not np.all(s >= jobs.submit_time.to_numpy()) or not np.all(e-s == jobs.duration.to_numpy()):
        raise AssertionError('Timing contract')
    capg = [int(x) for x in nodes.gpu_capacity_num]
    capc = [int(x) for x in nodes.cpu_units]
    freeg, freec = capg.copy(), capc.copy()
    demands = []
    for j, (q, c, w, model) in enumerate(jobs[['gpu_request','cpu_units','worker_num','gpu_model']].itertuples(index=False, name=None)):
        seen = set(); demand = []
        for m, count in plans[j]:
            if (not isinstance(m, (int,np.integer)) or not isinstance(count, (int,np.integer))
                or isinstance(count, (bool,np.bool_)) or not 0 <= m < len(nodes)
                or count <= 0 or m in seen or nodes.gpu_model.iloc[m] != model):
                raise AssertionError('Placement contract: invalid or duplicate node')
            seen.add(m)
            demand.append((int(m), int(count)*int(q), int(count)*int(c)))
        if sum(count for _, count in plans[j]) != w:
            raise AssertionError('Worker count')
        demands.append(demand)
    running = set()
    events = sorted([(int(t), 0, j) for j,t in enumerate(e)] + [(int(t), 1, j) for j,t in enumerate(s)])
    for _, kind, j in events:
        if kind == 0:
            if j not in running:
                raise AssertionError('Completion without running gang')
            running.remove(j)
            for m,g,c in demands[j]:
                freeg[m] += g; freec[m] += c
        else:
            if j in running or any(g > freeg[m] or c > freec[m] for m,g,c in demands[j]):
                raise AssertionError('Independent capacity replay failed')
            running.add(j)
            for m,g,c in demands[j]:
                freeg[m] -= g; freec[m] -= c
        # Only touched nodes can change; all other bounds remain invariant.
        if any(not (0 <= freeg[m] <= capg[m] and 0 <= freec[m] <= capc[m]) for m,_,_ in demands[j]):
            raise AssertionError('Resource bounds')
    if running or freeg != capg or freec != capc:
        raise AssertionError('Final allocation is not zero')


def validate_persisted(nodes, jobs, times_path, placements_path):
    """Strict CSV adapter to validate(), using raw attributes, never reported demand.

    Decimal parsing precedes int conversion; no truncation or float rounding.
    """
    from decimal import Decimal, InvalidOperation
    def read(path, columns):
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        if not set(columns) <= set(frame):
            raise ValueError('Missing required fields')
        for col in columns:
            if col == 'gpu_model':
                continue
            parsed = []
            for value in frame[col]:
                try:
                    d = Decimal(value)
                except InvalidOperation as exc:
                    raise ValueError('Non-numeric field') from exc
                if not d.is_finite() or d != d.to_integral_value() or abs(d) >= 2**63:
                    raise ValueError('Non-finite, fractional or out-of-range integer')
                parsed.append(int(d))
            frame[col] = pd.Series(parsed, dtype='int64')
        return frame
    attrs = ['job_name','gpu_model','submit_time','duration','worker_num','gpu_request','cpu_units']
    times = read(times_path, attrs + ['start','finish','wait'])
    ledger = read(placements_path, ['job_name','node_name','workers'])
    raw = jobs.sort_values('job_name').reset_index(drop=True)
    times = times.sort_values('job_name').reset_index(drop=True)
    if len(times) != len(raw) or times.job_name.duplicated().any() or set(times.job_name) != set(raw.job_name):
        raise ValueError('Timing ID multiplicity/set mismatch')
    for col in attrs:
        if not np.array_equal(times[col].to_numpy(), raw[col].to_numpy()):
            raise ValueError('Raw attribute mismatch: ' + col)
    if not np.array_equal(times.wait.to_numpy(), (times.start-times.submit_time).to_numpy()):
        raise ValueError('Reported wait mismatch')
    if ledger.duplicated(['job_name','node_name']).any() or (ledger.workers <= 0).any():
        raise ValueError('Duplicate placement pair or nonpositive workers')
    if set(ledger.job_name) != set(raw.job_name) or not set(ledger.node_name) <= set(nodes.node_name):
        raise ValueError('Placement ID mismatch')
    node_index = {int(name): i for i,name in enumerate(nodes.node_name)}
    groups = {int(j): [(node_index[int(n)], int(w)) for n,w in g[['node_name','workers']].itertuples(index=False,name=None)] for j,g in ledger.groupby('job_name')}
    plans = [groups[int(j)] for j in raw.job_name]
    validate(nodes, raw, times.start.to_numpy(), times.finish.to_numpy(), plans)
    return {'status':'PASS', 'jobs':len(raw), 'ledger_rows':len(ledger),
            'input_identity':'PASS', 'timing':'PASS', 'atomic_capacity_replay':'PASS', 'final_allocation_zero':'PASS'}


def validate_reservations(nodes: pd.DataFrame, jobs: pd.DataFrame, result: dict, *, progress=None) -> None:
    """Replay promise certificates in one event-ordered ledger pass.

    The previous implementation rebuilt every snapshot by scanning the prefix
    of ``events`` for every promise and every crossing.  This implementation
    keeps one current node ledger and releases each live context after its
    fulfillment and matching protected start have both been verified.  Crossing
    certificates are checked at their event position, before the corresponding
    start event mutates the ledger, so the independent checks retain the exact
    FIXED/FLEX semantics without quadratic prefix scans.
    """
    for field in ("reservations", "events"):
        if not isinstance(result.get(field), list) or any(
                not isinstance(item, dict) for item in result[field]):
            raise AssertionError(f"reservation replay requires explicit {field} list of records")
    reservations = result["reservations"]
    events = result["events"]
    evidence_schema = int(result.get("reservation_evidence_schema_version", 1))
    if reservations and evidence_schema != 2:
        raise AssertionError("legacy reservation evidence schema is not silently reinterpreted")
    starts = np.asarray(result["starts"], dtype=np.int64)
    ends = np.asarray(result["ends"], dtype=np.int64)
    plans_raw = result["plans"]
    if len(starts) != len(jobs) or len(ends) != len(jobs) or len(plans_raw) != len(jobs):
        raise AssertionError("reservation replay requires a complete schedule")
    caps_g = nodes.gpu_capacity_num.to_numpy(dtype=np.int64)
    caps_c = nodes.cpu_units.to_numpy(dtype=np.int64)
    job_g = jobs.gpu_request.to_numpy(dtype=np.int64)
    job_c = jobs.cpu_units.to_numpy(dtype=np.int64)
    job_w = jobs.worker_num.to_numpy(dtype=np.int64)
    job_names = jobs.job_name.to_numpy()
    ids = {int(name): i for i, name in enumerate(job_names)}
    plans: list[tuple[tuple[int, int], ...]] = []
    for raw in plans_raw:
        try:
            plan = tuple((int(node), int(count)) for node, count in raw)
        except (TypeError, ValueError):
            raise AssertionError("invalid placement ledger")
        plans.append(plan)

    # Validate promise records up front.  Missing/null evidence is an error,
    # including when issuance events exist but reservations was emptied.
    contexts: dict[str, dict] = {}
    for promise in reservations:
        if int(promise.get("evidence_schema_version", 1)) != evidence_schema or evidence_schema != 2:
            raise AssertionError("unsupported or inconsistent reservation evidence schema")
        pid = promise.get("promise_id")
        if not isinstance(pid, str) or not pid or pid in contexts:
            raise AssertionError("duplicate or missing promise_id")
        try:
            protected_name = int(promise["protected_job_name"])
            protected = ids[protected_name]
            issued = int(promise["issued_time"])
            promised_r = int(promise["promised_R"])
        except (KeyError, TypeError, ValueError):
            raise AssertionError("incomplete promise record")
        initial_raw = promise.get("initial_placement_witness")
        if not isinstance(initial_raw, list):
            raise AssertionError("immutable initial placement witness is missing")
        try:
            initial_witness = tuple((int(node), int(count)) for node, count in initial_raw)
        except (TypeError, ValueError):
            raise AssertionError("invalid immutable initial placement witness")
        if (any(node < 0 or node >= len(nodes) or count <= 0 for node, count in initial_witness)
                or sum(count for _, count in initial_witness) != int(job_w[protected])):
            raise AssertionError("invalid immutable initial placement witness")
        updates = promise.get("certificate_updates")
        if not isinstance(updates, list) or any(not isinstance(item, dict) for item in updates):
            raise AssertionError("certificate_updates must be an explicit list")
        recorded_updates = [item for item in updates if "job" in item]
        fulfillment_updates = [item for item in updates if item.get("event") == "fulfillment"]
        if len(fulfillment_updates) != 1:
            raise AssertionError("fulfillment certificate update is missing or duplicated")
        accepted_raw = promise.get("accepted_backfill_ids")
        if not isinstance(accepted_raw, list) or len({int(x) for x in accepted_raw}) != len(accepted_raw):
            raise AssertionError("accepted backfill evidence is invalid")
        contexts[pid] = {
            "promise": promise, "protected": protected, "issued": issued,
            "R": promised_r, "initial_witness": initial_witness,
            "updates": recorded_updates, "update_pos": 0,
            "accepted": {int(x) for x in accepted_raw}, "started": set(),
            "future_g": None, "future_c": None,
            "witness": initial_witness, "version": None,
            "fulfilled": None, "issued_seen": False,
        }

    def check_snapshot(promise: dict, key: str, gpu, cpu) -> None:
        """Accept a live dense snapshot or its compact immutable digest."""
        recorded = promise.get(key)
        if isinstance(recorded, dict) and "gpu" in recorded and "cpu" in recorded:
            if gpu.tolist() != list(recorded.get("gpu", [])) or cpu.tolist() != list(recorded.get("cpu", [])):
                raise AssertionError(f"{key} does not replay from event order")
            return
        digests = promise.get("snapshot_sha256", {})
        expected = digests.get(key) if isinstance(digests, dict) else None
        if not isinstance(expected, str) or expected != _snapshot_hash(gpu, cpu):
            raise AssertionError(f"{key} snapshot evidence is missing or inconsistent")

    issued_ids: set[str] = set()
    fulfilled_ids: set[str] = set()
    crossing_allowed = {"SPT-URGENT-FIXED", "SPT-URGENT-FLEX", "EASY-NR"}
    policy = str(result.get("policy", ""))
    current_g, current_c = caps_g.copy(), caps_c.copy()
    active: dict[int, tuple[tuple[int, int], ...]] = {}
    # The scheduler permits at most one pending promise per pool.  Keep that
    # invariant explicit during replay so start events do not rescan every
    # historical context (which made validation quadratic in the number of
    # promises). Completed contexts are audited then released at protected start.
    active_promise_id: str | None = None
    awaiting_start: str | None = None
    completed_ids: set[str] = set()
    seen_starts = np.zeros(len(jobs), dtype=bool)
    seen_finishes = np.zeros(len(jobs), dtype=bool)
    last_time = -1

    def apply_job(j: int, sign: int) -> None:
        for node, count in plans[j]:
            current_g[node] += sign * count * int(job_g[j])
            current_c[node] += sign * count * int(job_c[j])
        if np.any(current_g < 0) or np.any(current_c < 0) \
                or np.any(current_g > caps_g) or np.any(current_c > caps_c):
            raise AssertionError("independent current resource replay failed")

    def finish_context(pid: str) -> None:
        ctx = contexts[pid]
        promise = ctx["promise"]
        if ctx["update_pos"] != len(ctx["updates"]):
            raise AssertionError("certificate update evidence is incomplete")
        accepted = ctx["accepted"]
        if accepted != ctx["started"]:
            raise AssertionError("accepted backfill evidence does not match start events")
        crossing_jobs = {int(u["job"]) for u in ctx["updates"]}
        if crossing_jobs != {j for j in accepted if int(ends[j]) > ctx["R"]}:
            raise AssertionError("crossing backfill certificate ids do not match allocations")
        if int(promise.get("state_version")) != int(ctx["version"]):
            raise AssertionError("promise final certificate version differs from replay")
        check_snapshot(promise, "future_free_at_R", ctx["future_g"], ctx["future_c"])
        final_witness = tuple((int(node), int(count))
                              for node, count in promise.get("placement_witness", []))
        if final_witness != ctx["witness"]:
            raise AssertionError("final witness differs from certificate replay")
        check_plan(ctx["future_g"], ctx["future_c"], int(job_g[ctx["protected"]]),
                   int(job_c[ctx["protected"]]), final_witness, int(job_w[ctx["protected"]]))
        if int(slots(ctx["future_g"], ctx["future_c"], int(job_g[ctx["protected"]]),
                     int(job_c[ctx["protected"]])).sum()) < int(job_w[ctx["protected"]]):
            raise AssertionError("future snapshot does not contain protected gang")
        if starts[ctx["protected"]] < 0 or starts[ctx["protected"]] > ctx["R"] \
                or ctx["fulfilled"] != int(starts[ctx["protected"]]):
            raise AssertionError("promise timing contract")
        completed_ids.add(pid)
        # The caller also clears its local ctx reference. No historical dense
        # arrays or copies of the active-job set survive this point.
        del contexts[pid]

    def report(action: str, count: int) -> None:
        if progress is not None:
            progress("reservation_replay", action, events_processed=count,
                     promises_issued=len(issued_ids), promises_completed=len(completed_ids),
                     live_dense_contexts=int(active_promise_id is not None or awaiting_start is not None),
                     live_dense_bytes=(2 * caps_g.nbytes if active_promise_id is not None
                                       or awaiting_start is not None else 0),
                     active_jobs=len(active))

    report("begin", 0)
    for event_index, item in enumerate(events):
        if event_index and event_index % 4096 == 0:
            report("progress", event_index)
        try:
            t = int(item["time"])
        except (KeyError, TypeError, ValueError):
            raise AssertionError("event has no valid time")
        if t < last_time:
            raise AssertionError("event order is not monotone")
        last_time = t
        kind = item.get("kind")
        if awaiting_start is not None:
            pending = contexts[awaiting_start]
            if (kind != "start" or item.get("job") != pending["protected"]
                    or t != pending["fulfilled"]):
                raise AssertionError("fulfillment must be followed by its protected start")
        if kind == "reservation_issued":
            pid = item.get("promise_id")
            if pid not in contexts or pid in issued_ids:
                raise AssertionError("reservation issuance is missing or duplicated")
            if active_promise_id is not None:
                raise AssertionError("overlapping pending promises")
            ctx = contexts[pid]
            if (t != ctx["issued"] or int(item.get("protected_job")) != ctx["protected"]
                    or int(item.get("promised_R")) != ctx["R"]):
                raise AssertionError("reservation issuance does not match its promise record")
            ctx["issued_seen"] = True
            ctx["version"] = int(item.get("state_version"))
            if ctx["version"] < 0:
                raise AssertionError("invalid issuance version")
            future_g, future_c = caps_g.copy(), caps_c.copy()
            for j in active:
                if int(ends[j]) > ctx["R"]:
                    for node, count in plans[j]:
                        future_g[node] -= count * int(job_g[j])
                        future_c[node] -= count * int(job_c[j])
            if np.any(future_g < 0) or np.any(future_c < 0):
                raise AssertionError("negative future snapshot at issuance")
            check_snapshot(ctx["promise"], "current_free_initial", current_g, current_c)
            check_snapshot(ctx["promise"], "future_free_initial", future_g, future_c)
            ctx["future_g"], ctx["future_c"] = future_g, future_c
            issued_ids.add(pid)
            active_promise_id = pid
            continue

        if kind == "certificate_update":
            pid = item.get("promise_id")
            if pid not in contexts or pid not in issued_ids or pid != active_promise_id:
                raise AssertionError("certificate has no prior promise issuance")
            ctx = contexts[pid]
            pos = ctx["update_pos"]
            if pos >= len(ctx["updates"]):
                raise AssertionError("certificate update evidence has extra event")
            recorded = ctx["updates"][pos]
            for key in ("time", "job", "state_version", "previous_state_version", "planner",
                        "plan", "future_delta", "head_witness"):
                if item.get(key) != recorded.get(key):
                    raise AssertionError("certificate event and record differ")
            try:
                j = int(item["job"])
                version = int(item["state_version"])
                previous = int(item["previous_state_version"])
            except (KeyError, TypeError, ValueError):
                raise AssertionError("invalid certificate update")
            if not 0 <= j < len(jobs) or j == ctx["protected"] or policy not in crossing_allowed:
                raise AssertionError("invalid crossing certificate job or policy")
            plan = plans[j]
            if tuple(tuple(x) for x in item.get("plan", [])) != plan:
                raise AssertionError("certificate plan differs from allocation ledger")
            if t != int(starts[j]) or int(ends[j]) <= ctx["R"]:
                raise AssertionError("invalid crossing certificate timing")
            if previous != ctx["version"] or version <= previous:
                raise AssertionError("certificate version chain is broken")
            check_plan(current_g, current_c, int(job_g[j]), int(job_c[j]), plan, int(job_w[j]))
            old_future_g, old_future_c = ctx["future_g"].copy(), ctx["future_c"].copy()
            delta_g = np.zeros_like(old_future_g)
            delta_c = np.zeros_like(old_future_c)
            for node, count in plan:
                delta_g[node] += count * int(job_g[j])
                delta_c[node] += count * int(job_c[j])
            future_g = old_future_g - delta_g
            future_c = old_future_c - delta_c
            if np.any(future_g < 0) or np.any(future_c < 0):
                raise AssertionError("certificate future snapshot is negative")
            mode = str(item.get("planner"))
            head_witness = tuple((int(node), int(count)) for node, count in item.get("head_witness", []))
            if mode == "fixed":
                if head_witness != ctx["witness"]:
                    raise AssertionError("FIXED certificate changed the protected witness")
                z_g = np.zeros_like(future_g); z_c = np.zeros_like(future_c)
                for node, count in ctx["witness"]:
                    z_g[node] += count * int(job_g[ctx["protected"]])
                    z_c[node] += count * int(job_c[ctx["protected"]])
                effective_g = np.minimum(current_g, old_future_g - z_g)
                effective_c = np.minimum(current_c, old_future_c - z_c)
                check_plan(effective_g, effective_c, int(job_g[j]), int(job_c[j]), plan, int(job_w[j]))
            elif mode == "flex":
                if policy == "SPT-URGENT-FIXED":
                    raise AssertionError("FIXED policy cannot use FLEX certificate")
                check_plan(future_g, future_c, int(job_g[ctx["protected"]]),
                           int(job_c[ctx["protected"]]), head_witness, int(job_w[ctx["protected"]]))
                if int(slots(future_g, future_c, int(job_g[ctx["protected"]]),
                             int(job_c[ctx["protected"]])).sum()) < int(job_w[ctx["protected"]]):
                    raise AssertionError("FLEX certificate loses protected head slots")
                ctx["witness"] = head_witness
            else:
                raise AssertionError("unknown crossing planner certificate")
            recorded_delta = item.get("future_delta")
            expected_gpu = {str(int(node)): int(-delta_g[int(node)]) for node in np.flatnonzero(delta_g)}
            expected_cpu = {str(int(node)): int(-delta_c[int(node)]) for node in np.flatnonzero(delta_c)}
            if (not isinstance(recorded_delta, dict)
                    or recorded_delta.get("gpu") != expected_gpu
                    or recorded_delta.get("cpu") != expected_cpu):
                raise AssertionError("certificate future delta does not match allocation")
            ctx["future_g"], ctx["future_c"] = future_g, future_c
            ctx["version"] = version
            ctx["update_pos"] += 1
            continue

        if kind == "reservation_fulfilled":
            pid = item.get("promise_id")
            if pid not in contexts or pid in fulfilled_ids:
                raise AssertionError("reservation fulfillment is missing or duplicated")
            ctx = contexts[pid]
            if (pid not in issued_ids or t > ctx["R"]
                    or int(item.get("protected_job")) != ctx["protected"]
                    or int(item.get("promised_R")) != ctx["R"]):
                raise AssertionError("reservation fulfillment does not match its promise")
            fulfillment = ctx["promise"].get("fulfillment", {})
            update = [u for u in ctx["promise"].get("certificate_updates", [])
                      if u.get("event") == "fulfillment"]
            if (fulfillment.get("status") != "FULFILLED" or int(fulfillment.get("time")) != t
                    or len(update) != 1 or int(update[0].get("time")) != t
                    or int(item.get("state_version")) != int(update[0].get("state_version"))):
                raise AssertionError("fulfillment certificate is inconsistent")
            ctx["fulfilled"] = t
            fulfilled_ids.add(pid)
            if active_promise_id != pid:
                raise AssertionError("fulfilled promise is not the active pending promise")
            active_promise_id = None
            awaiting_start = pid
            continue

        if kind == "start":
            try:
                j = int(item["job"])
            except (KeyError, TypeError, ValueError):
                raise AssertionError("invalid start event")
            if not 0 <= j < len(jobs) or seen_starts[j] or j in active or t != int(starts[j]):
                raise AssertionError("start event disagrees with timing ledger")
            seen_starts[j] = True
            if active_promise_id is not None:
                ctx = contexts[active_promise_id]
                if j == ctx["protected"]:
                    raise AssertionError("protected start has no prior fulfillment")
                if (ctx["issued_seen"] and ctx["fulfilled"] is None
                        and ctx["issued"] <= t < ctx["R"]
                        and j != ctx["protected"]):
                    ctx["started"].add(j)
            apply_job(j, -1)
            active[j] = plans[j]
            if awaiting_start is not None:
                finish_context(awaiting_start)
                awaiting_start = None
                ctx = None  # release the final local reference to dense arrays
            continue

        if kind == "finish":
            try:
                j = int(item["job"])
            except (KeyError, TypeError, ValueError):
                raise AssertionError("invalid finish event")
            if not 0 <= j < len(jobs) or seen_finishes[j] or j not in active or t != int(ends[j]):
                raise AssertionError("finish event disagrees with timing ledger")
            seen_finishes[j] = True
            apply_job(j, 1)
            del active[j]

    if active_promise_id is not None:
        raise AssertionError("pending promise has no fulfillment")
    if awaiting_start is not None:
        raise AssertionError("fulfillment has no protected start")
    if contexts or issued_ids != fulfilled_ids or issued_ids != completed_ids:
        raise AssertionError("reservation evidence is missing issuance or fulfillment")
    if not seen_starts.all() or not seen_finishes.all():
        raise AssertionError("start/finish evidence is incomplete")
    report("end", len(events))
    if active or not np.array_equal(current_g, caps_g) or not np.array_equal(current_c, caps_c):
        raise AssertionError("final allocation is not fully released")



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
