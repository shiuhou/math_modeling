"""M0/M1 regression cases for planner, promises, timers and independent replay."""
import copy
import unittest

import numpy as np
import pandas as pd

from gpu_scheduling.placement import check_plan, plan_first_fit, slots
from gpu_scheduling.simulator import simulate_pool
from gpu_scheduling.validation import validate_reservations


def nodes(gpus=(1,), cpus=(8,)):
    return pd.DataFrame({"node_name": list(range(len(gpus))), "gpu_model": ["X"] * len(gpus),
                         "gpu_capacity_num": list(gpus), "cpu_num": list(cpus),
                         "cpu_units": [int(x * 100) for x in cpus]})


def jobs(ids, durations, cpus=None, workers=None, submits=None):
    cpus = cpus or [1] * len(ids)
    workers = workers or [1] * len(ids)
    submits = submits or [0] * len(ids)
    return pd.DataFrame({"job_name": ids, "gpu_model": ["X"] * len(ids),
                         "gpu_request": [1] * len(ids), "cpu_units": [int(x * 100) for x in cpus],
                         "worker_num": workers, "submit_time": submits, "duration": durations})


class M1Checks(unittest.TestCase):
    def test_pure_planner_and_atomic_gang(self):
        fg = np.array([2, 1], dtype=np.int64)
        fc = np.array([800, 800], dtype=np.int64)
        before = (fg.copy(), fc.copy())
        plan = plan_first_fit(fg, fc, 1, 400, 3)
        self.assertIsNotNone(plan)
        check_plan(fg, fc, 1, 400, plan, 3)
        np.testing.assert_array_equal(fg, before[0])
        np.testing.assert_array_equal(fc, before[1])
        self.assertEqual(slots(np.array([1, 1]), np.array([800, 800]), 1, 1000).sum(), 0)

    def test_cpu_boundaries_and_true_infeasible(self):
        nd = nodes((2,), (8,))
        r = simulate_pool(nd, jobs([0, 1], [2, 2], cpus=[4, 4]), "FCFS-HOL")
        self.assertEqual(r["starts"].tolist(), [0, 0])
        nd127 = nodes((1,), (127,))
        self.assertEqual(simulate_pool(nd127, jobs([0], [1], cpus=[127]), "FCFS-HOL")["starts"].tolist(), [0])
        with self.assertRaisesRegex(ValueError, "infeasible"):
            simulate_pool(nodes((1,), (8,)), jobs([0], [1], cpus=[8], workers=[2]), "FCFS-HOL")

    def test_easy_time_finish_r_and_crossing_backfill(self):
        nd = nodes((1, 1), (1, 1))
        jj = pd.DataFrame({"job_name": [0, 1, 2], "gpu_model": ["X"] * 3,
                           "gpu_request": [1, 1, 1], "cpu_units": [100, 100, 100],
                           "worker_num": [1, 2, 1], "submit_time": [0, 0, 1],
                           "duration": [10, 1, 11]})
        r = simulate_pool(nd, jj, "EASY-TIME", theta_seconds=2)
        self.assertEqual(r["starts"].tolist(), [0, 10, 11])
        self.assertGreaterEqual(len(r["reservations"]), 1)
        promise = r["reservations"][0]
        self.assertEqual(promise["promised_R"], 10)
        self.assertEqual(promise["fulfillment"]["status"], "FULFILLED")
        validate_reservations(nd, r["jobs"], r)

    def test_k_only_counts_bypass_candidates(self):
        for policy in ("SPT-FILL", "SGW-FILL", "EASY-TIME", "SPT-URGENT-TIME"):
            nd = nodes((1, 1), (1, 1))
            result = simulate_pool(nd, jobs([0, 1], [10, 10]), policy,
                                   reservation_k=1, theta_seconds=0)
            self.assertEqual(result["starts"].tolist(), [0, 0], policy)
        nd = nodes((1, 1), (1, 1))
        urgent = simulate_pool(nd, jobs([0, 1], [10, 10]), "SPT-URGENT-TIME",
                               reservation_k=1, theta_seconds=0)
        self.assertFalse(any(x["kind"] == "budget_exhausted" for x in urgent["events"]))

        # With 201 idle nodes, K=200 must not stop the 201-job feasible prefix;
        # K=200/201 are both covered explicitly.
        nd = nodes(tuple([1] * 201), tuple([1] * 201))
        for k in (200, 201):
            result = simulate_pool(nd, jobs(list(range(201)), [10] * 201),
                                   "SPT-FILL", reservation_k=k)
            self.assertTrue(np.all(result["starts"] == 0))

    def test_easy_time_scans_same_timestamp_and_accepts_finish_equal_r(self):
        nd = nodes((1, 1), (1, 1))
        jj = pd.DataFrame({"job_name": [0, 1, 2], "gpu_model": ["X"] * 3,
                           "gpu_request": [1, 1, 1], "cpu_units": [100, 100, 100],
                           "worker_num": [1, 2, 1], "submit_time": [0, 1, 1],
                           "duration": [10, 1, 2]})
        result = simulate_pool(nd, jj, "EASY-TIME")
        self.assertEqual(result["starts"].tolist(), [0, 10, 1])
        jj.loc[2, "duration"] = 9
        equal = simulate_pool(nd, jj, "EASY-TIME")
        self.assertEqual(equal["starts"].tolist(), [0, 10, 1])
        self.assertIn(2, equal["reservations"][0]["accepted_backfill_ids"])

    def test_urgent_timer_is_exact_and_protected_not_k_cropped(self):
        nd = nodes((1,), (1,))
        # SPT starts the six-second job. The ten-second head is still blocked
        # when its arrival+theta timer fires at t=4 and is promised for R=6.
        jj = jobs([0, 1], [10, 6])
        r = simulate_pool(nd, jj, "SPT-URGENT-HOL", theta_seconds=4, reservation_k=1)
        self.assertEqual(r["starts"].tolist(), [6, 0])
        self.assertEqual(r["reservations"][0]["issued_time"], 4)
        self.assertEqual(r["reservations"][0]["promised_R"], 6)
        self.assertTrue(any(x["kind"] == "timer_threshold" and x["time"] == 4 for x in r["events"]))
        validate_reservations(nd, r["jobs"], r)

    def test_time_promise_is_immutable_and_replay_is_independent(self):
        nd = nodes((1,), (1,))
        jj = jobs([0, 1, 2], [10, 2, 2])
        r = simulate_pool(nd, jj, "SPT-URGENT-TIME", theta_seconds=1)
        validate_reservations(nd, r["jobs"], r)
        self.assertTrue(all(x["promised_R"] >= x["issued_time"] for x in r["reservations"]))
        bad = copy.deepcopy(r)
        if bad["reservations"]:
            bad["reservations"][0]["future_free_at_R"]["gpu"][0] += 1
            with self.assertRaises(AssertionError):
                validate_reservations(nd, bad["jobs"], bad)

        issued_mismatch = copy.deepcopy(r)
        if issued_mismatch["reservations"]:
            promise = issued_mismatch["reservations"][0]
            protected = int(promise["protected_job"])
            promise["promised_R"] += 1
            issued_mismatch["starts"][protected] += 1
            issued_mismatch["ends"][protected] += 1
            with self.assertRaises(AssertionError):
                validate_reservations(nd, issued_mismatch["jobs"], issued_mismatch)

        missing_record = copy.deepcopy(r)
        if missing_record["reservations"]:
            missing_record["reservations"] = []
            with self.assertRaises(AssertionError):
                validate_reservations(nd, missing_record["jobs"], missing_record)

    def test_event_mode_is_explicit_and_shared_ticks_are_not_policy_implicit(self):
        nd = nodes((1,), (1,))
        jj = jobs([0, 1], [3, 2])
        shared = simulate_pool(nd, jj, "SPT-FILL", theta_seconds=1,
                               event_mode="shared-timer")
        historical = simulate_pool(nd, jj, "SPT-FILL", theta_seconds=1,
                                   event_mode="arrival-completion-only")
        self.assertEqual(shared["event_mode"], "shared-timer")
        self.assertEqual(historical["event_mode"], "arrival-completion-only")
        self.assertTrue(any(x["kind"] == "timer_threshold" for x in shared["events"]))
        self.assertFalse(any(x["kind"] == "timer_threshold" for x in historical["events"]))

    def test_policy_aliases_and_input_order_are_deterministic(self):
        nd = nodes((2, 1), (1, 1))
        jj = jobs([0, 1, 2], [3, 2, 1], workers=[1, 1, 1])
        a = simulate_pool(nd, jj.iloc[[2, 0, 1]], "SPT-FILL")
        b = simulate_pool(nd, jj, "SPT-FILL")
        self.assertEqual(a["starts"].tolist(), b["starts"].tolist())
        alias = simulate_pool(nd, jj, "SJF-HOL")
        canonical = simulate_pool(nd, jj, "SPT-HOL")
        self.assertEqual(alias["starts"].tolist(), canonical["starts"].tolist())


if __name__ == "__main__":
    unittest.main()
