"""M2-B certificate replay regression cases.

These fixtures intentionally exercise the persisted certificate protocol rather
than a scheduler's own safety predicate.  In particular, a promise can retain
the witness issued at R while later FLEX updates replace the witness used for
future checks.
"""
import copy
import unittest

import numpy as np
import pandas as pd

from gpu_scheduling.simulator import simulate_pool
from gpu_scheduling.validation import validate_reservations


def _nodes():
    return pd.DataFrame({
        "node_name": [0, 1, 2, 3], "gpu_model": ["X"] * 4,
        "gpu_capacity_num": [1, 1, 1, 1], "cpu_num": [1, 1, 1, 1],
        "cpu_units": [100, 100, 100, 100],
    })


def _fixed_then_flex_fixture():
    # A occupies node 0 until R=10.  The protected H initially uses nodes
    # 0+1.  C1 is a FIXED crossing on node 3; C2 then allows FLEX to move H to
    # nodes 0+2.  The original R and its fulfillment remain unchanged.
    jobs = pd.DataFrame({
        "job_name": [0, 1, 2, 3], "gpu_model": ["X"] * 4,
        "gpu_request": [1, 1, 1, 1], "cpu_units": [100] * 4,
        "worker_num": [1, 2, 1, 1], "submit_time": [0, 0, 1, 2],
        "duration": [10, 1, 20, 20],
    })
    return jobs, {
        "jobs": jobs, "starts": np.array([0, 10, 1, 2], dtype=np.int64),
        "ends": np.array([10, 11, 21, 22], dtype=np.int64),
        "plans": [[(0, 1)], [(0, 1), (2, 1)], [(3, 1)], [(1, 1)]],
        "policy": "SPT-URGENT-FLEX", "theta_seconds": 0,
        "reservation_k": 200, "event_mode": "shared-timer",
        "reservations": [{
            "promise_id": "promise-1", "protected_job": 1,
            "protected_job_name": 1, "issued_time": 1, "promised_R": 10,
            "current_free_initial": {"gpu": [0, 1, 1, 1], "cpu": [0, 100, 100, 100]},
            "future_free_initial": {"gpu": [1, 1, 1, 1], "cpu": [100, 100, 100, 100]},
            "future_free_at_R": {"gpu": [1, 0, 1, 0], "cpu": [100, 0, 100, 0]},
            "initial_placement_witness": [[0, 1], [1, 1]],
            "placement_witness": [[0, 1], [2, 1]], "state_version": 3,
            "certificate_updates": [
                {"time": 1, "job": 2, "state_version": 2,
                 "previous_state_version": 1, "planner": "fixed",
                 "plan": [[3, 1]],
                 "future_delta": {"gpu": {"3": -1}, "cpu": {"3": -100}},
                 "head_witness": [[0, 1], [1, 1]]},
                {"time": 2, "job": 3, "state_version": 3,
                 "previous_state_version": 2, "planner": "flex",
                 "plan": [[1, 1]],
                 "future_delta": {"gpu": {"1": -1}, "cpu": {"1": -100}},
                 "head_witness": [[0, 1], [2, 1]]},
                {"time": 10, "event": "fulfillment", "state_version": 4},
            ],
            "accepted_backfill_ids": [2, 3],
            "fulfillment": {"status": "FULFILLED", "time": 10},
            "policy": "SPT-URGENT-FLEX", "planner": "flex",
        }],
        "events": [
            {"time": 0, "kind": "start", "job": 0, "protected": False},
            {"time": 1, "kind": "reservation_issued", "promise_id": "promise-1",
             "protected_job": 1, "promised_R": 10, "state_version": 1},
            {"time": 1, "kind": "certificate_update", "promise_id": "promise-1",
             "time": 1, "job": 2, "state_version": 2, "previous_state_version": 1,
             "planner": "fixed", "plan": [[3, 1]],
             "future_delta": {"gpu": {"3": -1}, "cpu": {"3": -100}},
             "head_witness": [[0, 1], [1, 1]]},
            {"time": 1, "kind": "start", "job": 2, "protected": False},
            {"time": 2, "kind": "certificate_update", "promise_id": "promise-1",
             "time": 2, "job": 3, "state_version": 3, "previous_state_version": 2,
             "planner": "flex", "plan": [[1, 1]],
             "future_delta": {"gpu": {"1": -1}, "cpu": {"1": -100}},
             "head_witness": [[0, 1], [2, 1]]},
            {"time": 2, "kind": "start", "job": 3, "protected": False},
            {"time": 10, "kind": "finish", "job": 0},
            {"time": 10, "kind": "reservation_fulfilled", "promise_id": "promise-1",
             "protected_job": 1, "promised_R": 10, "state_version": 4},
            {"time": 10, "kind": "start", "job": 1, "protected": True},
            {"time": 11, "kind": "finish", "job": 1},
            {"time": 21, "kind": "finish", "job": 2},
            {"time": 22, "kind": "finish", "job": 3},
        ],
        "cost": {},
    }


class M2BCertificateReplay(unittest.TestCase):
    def test_fixed_then_flex_replays_immutable_initial_witness(self):
        jobs, result = _fixed_then_flex_fixture()
        validate_reservations(_nodes(), jobs, result)
        promise = result["reservations"][0]
        self.assertEqual(promise["promised_R"], 10)
        self.assertEqual(promise["fulfillment"]["time"], 10)
        self.assertNotEqual(promise["initial_placement_witness"], promise["placement_witness"])

        # Replacing the immutable witness with the final FLEX witness makes
        # the first update semantically impossible and must be rejected.
        bad = copy.deepcopy(result)
        bad["reservations"][0]["initial_placement_witness"] = [[0, 1], [2, 1]]
        with self.assertRaises(AssertionError):
            validate_reservations(_nodes(), jobs, bad)

    def test_fake_fixed_and_missing_or_reordered_updates_are_rejected(self):
        jobs, result = _fixed_then_flex_fixture()
        fake = copy.deepcopy(result)
        fake["events"][4]["planner"] = "fixed"
        fake["reservations"][0]["certificate_updates"][1]["planner"] = "fixed"
        with self.assertRaises(AssertionError):
            validate_reservations(_nodes(), jobs, fake)

        for mutate in ("delete", "reorder", "delta"):
            bad = copy.deepcopy(result)
            if mutate == "delete":
                bad["events"].pop(2)
            elif mutate == "reorder":
                bad["events"][2], bad["events"][4] = bad["events"][4], bad["events"][2]
            else:
                bad["events"][2]["future_delta"]["gpu"]["3"] = 0
                bad["reservations"][0]["certificate_updates"][0]["future_delta"]["gpu"]["3"] = 0
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError):
                validate_reservations(_nodes(), jobs, bad)

    def test_scheduler_records_initial_witness_and_sparse_deltas(self):
        nd = pd.DataFrame({"node_name": [0, 1, 2], "gpu_model": ["X"] * 3,
                           "gpu_capacity_num": [2, 1, 1], "cpu_num": [1, 2, 2],
                           "cpu_units": [100, 200, 200]})
        jj = pd.DataFrame({"job_name": [0, 1, 2], "gpu_model": ["X"] * 3,
                           "gpu_request": [1, 1, 2], "cpu_units": [200, 100, 0],
                           "worker_num": [2, 2, 1], "submit_time": [0, 0, 1],
                           "duration": [10, 10, 20]})
        result = simulate_pool(nd, jj, "SPT-URGENT-FLEX", theta_seconds=0)
        promise = result["reservations"][0]
        self.assertIn("initial_placement_witness", promise)
        self.assertTrue(all("future_delta" in u for u in promise["certificate_updates"] if "job" in u))
        self.assertTrue(all("future_free_at_R" not in u for u in promise["certificate_updates"] if "job" in u))
        validate_reservations(nd, result["jobs"], result)

    def test_null_reservations_with_issuance_is_not_empty_evidence(self):
        nd = _nodes()
        jobs, result = _fixed_then_flex_fixture()
        bad = copy.deepcopy(result)
        bad["reservations"] = None
        with self.assertRaises(AssertionError):
            validate_reservations(nd, jobs, bad)


if __name__ == "__main__":
    unittest.main()
