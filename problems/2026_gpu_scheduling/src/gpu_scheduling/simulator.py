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
    "EASY-TIME": "EASY-TIME", "SPT-URGENT-HOL": "SPT-URGENT-HOL",
    "SPT-URGENT-TIME": "SPT-URGENT-TIME",
}
M1_POLICIES = frozenset(POLICY_ALIASES.values()) - {"FCFS-HOL", "SPT-HOL"}
FILL_POLICIES = frozenset({"SPT-FILL", "SGW-FILL", "EASY-TIME", "SPT-URGENT-TIME"})
URGENT_POLICIES = frozenset({"SPT-URGENT-HOL", "SPT-URGENT-TIME"})


def canonical_policy(policy: str) -> str:
    try:
        return POLICY_ALIASES[str(policy)]
    except KeyError as exc:
        raise ValueError(f"unknown policy: {policy}") from exc


def _priority(j: int, policy: str, arr, dur, workers, reqg) -> tuple:
    if policy in ("FCFS-HOL", "EASY-TIME"):
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
    arrivals = finished = decisions = peak_queue = 0
    state_version = 0
    reservation: dict | None = None
    reservations: list[dict] = []
    events: list[dict] = []
    timers: list[tuple[int, int]] = []
    urgent: set[int] = set()
    m1 = policy in M1_POLICIES

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
        }
        reservations.append(reservation)
        event("reservation_issued", now, promise_id=reservation["promise_id"], protected_job=int(protected), promised_R=int(chosen_r))
        return True

    def commit(j: int, now: int, plan: PlacementPlan, protected: bool = False) -> None:
        nonlocal state_version, reservation
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
            if int(ends[j]) > int(reservation["promised_R"]):
                raise AssertionError("M1 TIME accepted a backfill crossing promised R")
            reservation["accepted_backfill_ids"].append(int(j))
            reservation["certificate_updates"].append({"time": int(now), "job": int(j), "state_version": int(state_version)})
        if protected:
            if reservation is None or j != int(reservation["protected_job"]):
                raise AssertionError("invalid protected commit")
            if now > int(reservation["promised_R"]):
                raise AssertionError("protected job started after promised R")
            reservation["fulfillment"] = {"status": "FULFILLED", "time": int(now)}
            reservation["certificate_updates"].append({"time": int(now), "event": "fulfillment", "state_version": int(state_version)})
            event("reservation_fulfilled", now, promise_id=reservation["promise_id"], protected_job=int(j))
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
        commit(protected, now, plan, protected=True)
        return True

    def trigger_timer(now: int) -> None:
        while timers and timers[0][0] == now:
            _, target = heapq.heappop(timers)
            event("timer_threshold", now, job=int(target), threshold=int(now))
            if policy in URGENT_POLICIES and target in waiting:
                urgent.add(target)

    def dispatch(now: int) -> None:
        nonlocal decisions, peak_queue
        if policy in ("FCFS-HOL", "SPT-HOL"):
            while waiting:
                j = waiting[0] if policy == "FCFS-HOL" else waiting[0][3]
                decisions += 1
                plan = current_plan(j)
                if plan is None:
                    return
                commit(j, now, plan)
            return
        attempts = 0
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
                        commit(j, now, plan, protected=True)
                        made = True
                    else:
                        # TIME policies may inspect safe candidates while the
                        # protected gang is waiting; HOL stops at the head.
                        seen.add(j)
                        blocked = policy not in FILL_POLICIES
                    if blocked:
                        break
                    continue
                if attempts >= reservation_k:
                    event("budget_exhausted", now, K=int(reservation_k))
                    return
                attempts += 1
                decisions += 1
                seen.add(j)
                plan = current_plan(j)
                if plan is None:
                    if policy in ("FCFS-HOL", "SPT-HOL"):
                        blocked = True
                        break
                    if policy == "EASY-TIME" and j == ordered[0] and reservation is None:
                        build_reservation(j, now)
                        blocked = True
                        break
                    if policy in URGENT_POLICIES and j in urgent and reservation is None:
                        build_reservation(j, now)
                        blocked = policy == "SPT-URGENT-HOL"
                        if blocked:
                            break
                    continue
                if reservation is not None and policy in FILL_POLICIES and int(now + dur[j]) > int(reservation["promised_R"]):
                    blocked = True
                    continue
                commit(j, now, plan)
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
            if m1:
                heapq.heappush(timers, (int(arr[arrivals] + theta_seconds), arrivals))
            arrivals += 1
        peak_queue = max(peak_queue, len(waiting))
        trigger_timer(t)
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
        "reservations": reservations, "events": events,
        "cost": {"planner_calls": int(decisions), "candidate_checks": int(decisions), "reservation_calls": len(reservations)},
    }
