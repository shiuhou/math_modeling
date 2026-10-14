"""The single event-driven scheduler used by the Problem B experiments.

The first two policies are the historical reservation-free baselines. The
remaining policies exercise the small Q2 M1 protection core. All policies
share the same node-level planner and event engine.
"""
from __future__ import annotations

import heapq
import math
from collections import defaultdict, deque
from typing import Iterable

import numpy as np
import pandas as pd

from .placement import PlacementPlan, apply_plan, check_plan, plan_first_fit, slots
from .validation import validate

POLICY_ALIASES = {
    "FCFS": "FCFS-HOL", "SJF-HOL": "SPT-HOL", "FCFS-HOL": "FCFS-HOL",
    "SPT-HOL": "SPT-HOL", "SPT-FILL": "SPT-FILL", "SGW-FILL": "SGW-FILL",
    "EASY-TIME": "EASY-TIME", "EASY-NR": "EASY-NR",
    "SPT-URGENT-HOL": "SPT-URGENT-HOL", "SPT-URGENT-TIME": "SPT-URGENT-TIME",
    "SPT-URGENT-FIXED": "SPT-URGENT-FIXED", "SPT-URGENT-FLEX": "SPT-URGENT-FLEX",
}
M1_POLICIES = frozenset(POLICY_ALIASES.values()) - {"FCFS-HOL", "SPT-HOL"}
FILL_POLICIES = frozenset({"SPT-FILL", "SGW-FILL", "EASY-TIME", "EASY-NR", "SPT-URGENT-TIME", "SPT-URGENT-FIXED", "SPT-URGENT-FLEX"})
URGENT_POLICIES = frozenset({"SPT-URGENT-HOL", "SPT-URGENT-TIME", "SPT-URGENT-FIXED", "SPT-URGENT-FLEX"})
FLEX_POLICIES = frozenset({"EASY-NR", "SPT-URGENT-FLEX"})
FIXED_POLICIES = frozenset({"SPT-URGENT-FIXED"})
TIME_POLICIES = frozenset({"EASY-TIME", "SPT-URGENT-TIME"})
EVENT_MODES = frozenset({"arrival-completion-only", "shared-timer"})


def canonical_policy(policy: str) -> str:
    try:
        return POLICY_ALIASES[str(policy)]
    except KeyError as exc:
        raise ValueError(f"unknown policy: {policy}") from exc


def _priority(j: int, policy: str, arr, dur, workers, reqg) -> tuple:
    if policy in ("FCFS-HOL", "EASY-TIME", "EASY-NR"):
        return (int(arr[j]), int(j))
    if policy == "SGW-FILL":
        return (int(workers[j] * reqg[j] * dur[j]), int(dur[j]), int(arr[j]), int(j))
    return (int(dur[j]), int(arr[j]), int(j))


def _ordered(wait: Iterable[int], policy: str, arr, dur, workers, reqg) -> list[int]:
    return sorted(wait, key=lambda j: _priority(j, policy, arr, dur, workers, reqg))


def _release(free_g, free_c, cap_g, cap_c, job, plan, reqg, reqc) -> None:
    apply_plan(free_g, free_c, int(reqg[job]), int(reqc[job]), plan, sign=1)
    if np.any(free_g > cap_g) or np.any(free_c > cap_c):
        raise AssertionError("over-release")


def simulate_pool(
    nodes: pd.DataFrame,
    jobs: pd.DataFrame,
    policy: str,
    *,
    theta_seconds: int = 4_860_000,
    reservation_k: int = 200,
    event_mode: str = "shared-timer",
) -> dict:
    """Simulate one GPU-model pool with node-local gang placement.

    ``FCFS`` and ``SJF-HOL`` are compatibility aliases with their historical
    completion/arrival behaviour. M1 policies add one immutable-R reservation
    and conservative TIME backfill to the same event engine.
    """
    requested_policy = str(policy)
    policy = canonical_policy(requested_policy)
    if theta_seconds < 0 or reservation_k <= 0:
        raise ValueError("theta_seconds must be nonnegative and K must be positive")
    if event_mode not in EVENT_MODES:
        raise ValueError(f"unknown event_mode: {event_mode}")
    nodes = nodes.sort_values("node_name", kind="stable").reset_index(drop=True)
    jobs = jobs.sort_values(["submit_time", "job_name"], kind="stable").reset_index(drop=True)
    if nodes.empty or jobs.empty:
        raise ValueError("A pool must contain nodes and jobs")
    if nodes.gpu_model.nunique() != 1 or jobs.gpu_model.nunique() != 1 or nodes.gpu_model.iloc[0] != jobs.gpu_model.iloc[0]:
        raise ValueError("simulate_pool requires one matching GPU model")
    n = len(jobs)
    arr = jobs.submit_time.to_numpy(dtype=np.int64)
    dur = jobs.duration.to_numpy(dtype=np.int64)
    reqg = jobs.gpu_request.to_numpy(dtype=np.int64)
    reqc = jobs.cpu_units.to_numpy(dtype=np.int64)
    workers = jobs.worker_num.to_numpy(dtype=np.int64)
    capg = nodes.gpu_capacity_num.to_numpy(dtype=np.int64)
    capc = nodes.cpu_units.to_numpy(dtype=np.int64)
    for q, c, w in jobs[["gpu_request", "cpu_units", "worker_num"]].drop_duplicates().itertuples(index=False, name=None):
        if int(slots(capg, capc, int(q), int(c)).sum()) < int(w):
            raise ValueError("Job infeasible on an empty pool; no jobs were dropped")

    free_g, free_c = capg.copy(), capc.copy()
    starts = np.full(n, -1, dtype=np.int64)
    ends = np.full(n, -1, dtype=np.int64)
    plans: list[list[tuple[int, int]] | None] = [None] * n
    waiting = deque() if policy == "FCFS-HOL" else ([] if policy == "SPT-HOL" else [])
    running_heap: list[tuple[int, int]] = []
    running: dict[int, tuple[int, list[tuple[int, int]]]] = {}
    arrivals = finished = decisions = peak_queue = bypass_checks_total = 0
    crossing_accepted = crossing_rejected = certificate_updates = reservation_rejects = 0
    state_version = 0
    reservation: dict | None = None
    reservations: list[dict] = []
    events: list[dict] = []
    timers: list[tuple[int, int]] = []
    urgent: set[int] = set()
    use_timers = event_mode == "shared-timer"

    def event(kind: str, t: int, **extra) -> None:
        events.append({"time": int(t), "kind": kind, **extra})

    def current_plan(j: int) -> PlacementPlan | None:
        return plan_first_fit(free_g, free_c, int(reqg[j]), int(reqc[j]), int(workers[j]))

    def build_reservation(protected: int, now: int) -> bool:
        nonlocal reservation, state_version
        if reservation is not None or current_plan(protected) is not None:
            return False
        projected_g, projected_c = free_g.copy(), free_c.copy()
        groups: dict[int, list[int]] = defaultdict(list)
        for j, (finish, _) in running.items():
            if finish > now:
                groups[int(finish)].append(j)
        chosen_r = None
        witness = None
        for candidate_r in sorted(groups):
            for j in groups[candidate_r]:
                _release(projected_g, projected_c, capg, capc, j, running[j][1], reqg, reqc)
            candidate = plan_first_fit(projected_g, projected_c, int(reqg[protected]), int(reqc[protected]), int(workers[protected]))
            if candidate is not None:
                chosen_r, witness = candidate_r, candidate
                break
        if chosen_r is None or witness is None:
            raise AssertionError("a feasible protected job has no reservation horizon")
        state_version += 1
        reservation = {
            "promise_id": f"promise-{len(reservations)+1}",
            "protected_job": int(protected),
            "protected_job_name": int(jobs.job_name.iloc[protected]),
            "issued_time": int(now),
            "promised_R": int(chosen_r),
            "current_free_initial": {"gpu": free_g.tolist(), "cpu": free_c.tolist()},
            "future_free_initial": {"gpu": projected_g.tolist(), "cpu": projected_c.tolist()},
            "future_free_at_R": {"gpu": projected_g.tolist(), "cpu": projected_c.tolist()},
            "placement_witness": [[int(m), int(w)] for m, w in witness.nodes],
            "state_version": int(state_version),
            "certificate_updates": [],
            "accepted_backfill_ids": [],
            "fulfillment": {"status": "PENDING", "time": None},
            "policy": policy,
            "planner": "flex" if policy in FLEX_POLICIES else ("fixed" if policy in FIXED_POLICIES else "time"),
        }
        reservations.append(reservation)
        event("reservation_issued", now, promise_id=reservation["promise_id"], protected_job=int(protected),
              promised_R=int(chosen_r), state_version=int(state_version))
        return True

    def _resource_delta(j: int, plan: PlacementPlan) -> tuple[np.ndarray, np.ndarray]:
        delta_g = np.zeros_like(free_g)
        delta_c = np.zeros_like(free_c)
        for node, count in plan.nodes:
            delta_g[int(node)] += int(count) * int(reqg[j])
            delta_c[int(node)] += int(count) * int(reqc[j])
        return delta_g, delta_c

    def _future_after_crossing(j: int, plan: PlacementPlan) -> tuple[np.ndarray, np.ndarray]:
        delta_g, delta_c = _resource_delta(j, plan)
        future_g = np.asarray(reservation["future_free_at_R"]["gpu"], dtype=np.int64).copy()
        future_c = np.asarray(reservation["future_free_at_R"]["cpu"], dtype=np.int64).copy()
        future_g -= delta_g
        future_c -= delta_c
        return future_g, future_c

    def _head_witness_capacity() -> tuple[np.ndarray, np.ndarray]:
        head = int(reservation["protected_job"])
        z_g = np.zeros_like(free_g)
        z_c = np.zeros_like(free_c)
        for node, count in reservation["placement_witness"]:
            z_g[int(node)] += int(count) * int(reqg[head])
            z_c[int(node)] += int(count) * int(reqc[head])
        return z_g, z_c

    def safe_plan(j: int, now: int) -> dict | None:
        """Construct one pure, node-level proposal; never mutate scheduler state."""
        nonlocal crossing_rejected, reservation_rejects
        plan = current_plan(j)
        if reservation is None:
            if plan is None:
                return None
            return {"plan": plan, "mode": "plain", "crossing": False,
                    "state_version": int(state_version)}
        if plan is None:
            reservation_rejects += 1
            return None
        promised_r = int(reservation["promised_R"])
        if int(now + dur[j]) <= promised_r:
            return {"plan": plan, "mode": "time", "crossing": False,
                    "state_version": int(state_version)}
        if policy in TIME_POLICIES:
            crossing_rejected += 1
            reservation_rejects += 1
            return None

        # FLEX first tries the actual current first-fit placement.  If it is
        # safe through R, the head witness may be rebuilt on the residual pool.
        if policy in FLEX_POLICIES:
            future_g, future_c = _future_after_crossing(j, plan)
            if np.all(future_g >= 0) and np.all(future_c >= 0):
                head = int(reservation["protected_job"])
                witness = plan_first_fit(future_g, future_c, int(reqg[head]), int(reqc[head]), int(workers[head]))
                if witness is not None:
                    return {"plan": plan, "mode": "flex", "crossing": True,
                            "future_g": future_g, "future_c": future_c,
                            "witness": witness, "state_version": int(state_version)}

        # FIXED is the conservative second attempt.  Reserve the existing Z
        # witness and expose only min(current_free, future_free_at_R-Z).
        z_g, z_c = _head_witness_capacity()
        future_g = np.asarray(reservation["future_free_at_R"]["gpu"], dtype=np.int64)
        future_c = np.asarray(reservation["future_free_at_R"]["cpu"], dtype=np.int64)
        effective_g = np.minimum(free_g, future_g - z_g)
        effective_c = np.minimum(free_c, future_c - z_c)
        fixed_plan = plan_first_fit(effective_g, effective_c, int(reqg[j]), int(reqc[j]), int(workers[j]))
        if fixed_plan is None:
            crossing_rejected += 1
            reservation_rejects += 1
            return None
        delta_g, delta_c = _resource_delta(j, fixed_plan)
        future_after_g, future_after_c = future_g - delta_g, future_c - delta_c
        if np.any(future_after_g < 0) or np.any(future_after_c < 0):
            crossing_rejected += 1
            reservation_rejects += 1
            return None
        return {"plan": fixed_plan, "mode": "fixed", "crossing": True,
                "future_g": future_after_g, "future_c": future_after_c,
                "witness": reservation["placement_witness"],
                "state_version": int(state_version)}

    def commit(j: int, now: int, proposal: dict, protected: bool = False) -> None:
        nonlocal state_version, reservation, crossing_accepted, certificate_updates
        plan = proposal["plan"]
        if int(proposal.get("state_version", state_version)) != int(state_version):
            raise AssertionError("stale placement proposal")
        check_plan(free_g, free_c, int(reqg[j]), int(reqc[j]), plan, int(workers[j]))
        apply_plan(free_g, free_c, int(reqg[j]), int(reqc[j]), plan, sign=-1)
        starts[j], ends[j] = int(now), int(now + dur[j])
        stored = [(int(m), int(w)) for m, w in plan.nodes]
        plans[j] = stored
        running[j] = (int(ends[j]), stored)
        heapq.heappush(running_heap, (int(ends[j]), int(j)))
        if policy == "FCFS-HOL":
            waiting.popleft()
        elif policy == "SPT-HOL":
            heapq.heappop(waiting)
        else:
            waiting.remove(j)
        state_version += 1
        if reservation is not None and j != int(reservation["protected_job"]):
            crossing = int(ends[j]) > int(reservation["promised_R"])
            if crossing and not proposal.get("crossing", False):
                raise AssertionError("crossing backfill lacks a safety certificate")
            if crossing and policy in TIME_POLICIES:
                raise AssertionError("TIME accepted a backfill crossing promised R")
            reservation["accepted_backfill_ids"].append(int(j))
            if crossing:
                future_g = np.asarray(proposal["future_g"], dtype=np.int64)
                future_c = np.asarray(proposal["future_c"], dtype=np.int64)
                witness = proposal["witness"]
                reservation["future_free_at_R"] = {"gpu": future_g.tolist(), "cpu": future_c.tolist()}
                reservation["placement_witness"] = [[int(m), int(w)] for m, w in
                                                       (witness.nodes if isinstance(witness, PlacementPlan) else witness)]
                update = {"time": int(now), "job": int(j), "state_version": int(state_version),
                          "previous_state_version": int(reservation["state_version"]),
                          "planner": str(proposal["mode"]),
                          "plan": [[int(m), int(w)] for m, w in plan.nodes],
                          "future_free_at_R": {"gpu": future_g.tolist(), "cpu": future_c.tolist()},
                          "head_witness": reservation["placement_witness"]}
                reservation["certificate_updates"].append(update)
                reservation["state_version"] = int(state_version)
                crossing_accepted += 1
                certificate_updates += 1
                event("certificate_update", now, promise_id=reservation["promise_id"], **update)
        if protected:
            if reservation is None or j != int(reservation["protected_job"]):
                raise AssertionError("invalid protected commit")
            if now > int(reservation["promised_R"]):
                raise AssertionError("protected job started after promised R")
            reservation["fulfillment"] = {"status": "FULFILLED", "time": int(now)}
            reservation["certificate_updates"].append({"time": int(now), "event": "fulfillment", "state_version": int(state_version)})
            event("reservation_fulfilled", now, promise_id=reservation["promise_id"],
                  protected_job=int(j), promised_R=int(reservation["promised_R"]),
                  state_version=int(state_version))
            reservation = None
        urgent.discard(j)
        event("start", now, job=int(j), protected=bool(protected))

    def due_protected(now: int) -> bool:
        if reservation is None or int(reservation["promised_R"]) != int(now):
            return False
        protected = int(reservation["protected_job"])
        if protected not in waiting:
            raise AssertionError("protected head disappeared before fulfillment")
        plan = current_plan(protected)
        if plan is None:
            raise AssertionError("promised reservation could not be fulfilled")
        commit(protected, now, {"plan": plan, "mode": "protected", "crossing": False,
                                "state_version": int(state_version)}, protected=True)
        return True

    def trigger_timer(now: int) -> None:
        while timers and timers[0][0] == now:
            _, target = heapq.heappop(timers)
            event("timer_threshold", now, job=int(target), threshold=int(now))
            if policy in URGENT_POLICIES and target in waiting:
                urgent.add(target)

    def dispatch(now: int) -> None:
        nonlocal decisions, bypass_checks_total, peak_queue
        if policy in ("FCFS-HOL", "SPT-HOL"):
            while waiting:
                j = waiting[0] if policy == "FCFS-HOL" else waiting[0][3]
                decisions += 1
                proposal = safe_plan(j, now)
                plan = proposal["plan"] if proposal is not None else None
                if plan is None:
                    return
                commit(j, now, proposal)
            return
        attempts = 0
        bypass_mode = False
        seen: set[int] = set()
        while waiting:
            peak_queue = max(peak_queue, len(waiting))
            if reservation is not None and int(reservation["promised_R"]) == int(now):
                due_protected(now)
                seen.clear()
                continue
            ordered = _ordered(waiting, policy, arr, dur, workers, reqg)
            if policy in URGENT_POLICIES and reservation is None and urgent:
                oldest = min(urgent, key=lambda j: (int(arr[j]), int(j)))
                ordered = [oldest] + [j for j in ordered if j != oldest]
            if reservation is not None:
                protected = int(reservation["protected_job"])
                if protected in waiting:
                    ordered = [protected] + [j for j in ordered if j != protected]
            made = False
            blocked = False
            for j in ordered:
                if j in seen:
                    continue
                if reservation is not None and j == int(reservation["protected_job"]):
                    plan = current_plan(j)
                    if plan is not None:
                        commit(j, now, {"plan": plan, "mode": "protected", "crossing": False,
                                        "state_version": int(state_version)}, protected=True)
                        made = True
                    else:
                        # TIME policies may inspect safe candidates while the
                        # protected gang is waiting; HOL stops at the head.
                        seen.add(j)
                        blocked = policy not in FILL_POLICIES
                        bypass_mode = True
                    if blocked:
                        break
                    continue
                # A feasible prefix is work-conserving and is free of the K
                # budget. K starts only after a blocked head creates a bypass
                # scan. Protected heads are handled above and are never here.
                if bypass_mode and attempts >= reservation_k:
                    event("budget_exhausted", now, K=int(reservation_k))
                    return
                if bypass_mode:
                    attempts += 1
                    bypass_checks_total += 1
                decisions += 1
                seen.add(j)
                proposal = safe_plan(j, now)
                plan = proposal["plan"] if proposal is not None else None
                if plan is None:
                    bypass_mode = True
                    if policy in ("FCFS-HOL", "SPT-HOL"):
                        blocked = True
                        break
                    if policy in ("EASY-TIME", "EASY-NR") and j == ordered[0] and reservation is None:
                        build_reservation(j, now)
                        # EASY-TIME continues the same timestamp scan; the
                        # newly protected head is exempt from K.
                        blocked = False
                        continue
                    urgent_head = j in urgent
                    if policy in URGENT_POLICIES and urgent_head and reservation is None:
                        build_reservation(j, now)
                        blocked = policy == "SPT-URGENT-HOL"
                        if blocked:
                            break
                    continue
                commit(j, now, proposal)
                made = True
                break
            if made:
                seen.clear()
                continue
            if blocked or not ordered or not any(j not in seen for j in ordered):
                return

    while arrivals < n or waiting or running:
        next_arrival = int(arr[arrivals]) if arrivals < n else math.inf
        next_finish = int(running_heap[0][0]) if running_heap else math.inf
        next_timer = int(timers[0][0]) if timers else math.inf
        next_r = int(reservation["promised_R"]) if reservation is not None else math.inf
        t = min(next_arrival, next_finish, next_timer, next_r)
        if not math.isfinite(t):
            raise RuntimeError("stuck queue: no future event")
        t = int(t)
        while running_heap and running_heap[0][0] == t:
            _, j = heapq.heappop(running_heap)
            if j not in running:
                continue
            _, plan = running.pop(j)
            _release(free_g, free_c, capg, capc, j, plan, reqg, reqc)
            finished += 1
            event("finish", t, job=int(j))
        while arrivals < n and int(arr[arrivals]) == t:
            if policy == "FCFS-HOL":
                waiting.append(arrivals)
            elif policy == "SPT-HOL":
                j = arrivals
                heapq.heappush(waiting, (int(dur[j]), int(arr[j]), int(jobs.job_name.iloc[j]), j))
            else:
                waiting.append(arrivals)
            if use_timers:
                heapq.heappush(timers, (int(arr[arrivals] + theta_seconds), arrivals))
            arrivals += 1
        peak_queue = max(peak_queue, len(waiting))
        trigger_timer(t)
        if event_mode == "arrival-completion-only" and policy in URGENT_POLICIES:
            # This mode samples the same age qualification only at external
            # arrival/completion epochs; it does not create threshold ticks.
            urgent.update(j for j in waiting if t - int(arr[j]) >= theta_seconds)
        if reservation is not None and int(reservation["promised_R"]) == t:
            due_protected(t)
        dispatch(t)

    if finished != n or not np.array_equal(free_g, capg) or not np.array_equal(free_c, capc):
        raise AssertionError("resource conservation or completion failure")
    validate(nodes, jobs, starts, ends, plans)
    return {
        "jobs": jobs, "starts": starts, "ends": ends, "plans": plans,
        "feasibility_checks": int(decisions), "peak_queue": int(peak_queue),
        "policy": policy, "policy_input": requested_policy,
        "theta_seconds": int(theta_seconds), "reservation_k": int(reservation_k),
        "event_mode": event_mode,
        "reservations": reservations, "events": events,
        "cost": {"planner_calls": int(decisions), "candidate_checks": int(decisions),
                 "bypass_candidate_checks": int(bypass_checks_total),
                 "reservation_calls": len(reservations),
                 "crossing_accepted": int(crossing_accepted),
                 "crossing_rejected": int(crossing_rejected),
                 "certificate_updates": int(certificate_updates),
                 "reservation_rejects": int(reservation_rejects)},
    }
