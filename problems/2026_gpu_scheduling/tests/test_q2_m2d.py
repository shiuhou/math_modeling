"""M2-D protected-HOL fast-path regressions."""
import unittest

import pandas as pd

from gpu_scheduling.data import prepare_data
from gpu_scheduling.simulator import simulate_pool
from gpu_scheduling.validation import validate, validate_reservations


class ProtectedHolFastPath(unittest.TestCase):
    def test_blocked_promise_skips_queue_sort_and_fulfills_at_R(self):
        nodes = pd.DataFrame({
            "node_name": [0, 1], "gpu_model": ["X", "X"],
            "gpu_capacity_num": [1, 1], "cpu_num": [1, 1],
        })
        rows = [
            {"job_name": 0, "gpu_model": "X", "gpu_request": 1,
             "cpu_request": 0.0, "worker_num": 1, "submit_time": 0, "duration": 100},
            {"job_name": 1, "gpu_model": "X", "gpu_request": 1,
             "cpu_request": 0.0, "worker_num": 2, "submit_time": 0, "duration": 200},
        ]
        # These jobs remain behind the protected two-worker head while the
        # first node is occupied.  Their arrivals and timer ticks must not
        # trigger a full SPT ordering pass in urgent HOL.
        rows.extend({"job_name": j, "gpu_model": "X", "gpu_request": 1,
                     "cpu_request": 0.0, "worker_num": 2, "submit_time": j,
                     "duration": 5} for j in range(2, 32))
        nodes, jobs = prepare_data(nodes, pd.DataFrame(rows))
        result = simulate_pool(nodes, jobs, "SPT-URGENT-HOL", theta_seconds=1,
                               reservation_k=200, event_mode="shared-timer")
        cost = result["cost"]
        self.assertGreater(cost["protected_hol_fastpath"], 0)
        self.assertGreater(cost["protected_hol_blocked"], 0)
        self.assertEqual(result["starts"][1], 100)
        self.assertEqual(result["ends"][1], 300)
        # The protected head is fulfilled before the next urgent head is
        # considered at the same release timestamp.
        fulfillment = next(e for e in result["events"]
                           if e["kind"] == "reservation_fulfilled"
                           and e["protected_job"] == 1)
        self.assertEqual(fulfillment["time"], 100)
        validate(nodes, result["jobs"], result["starts"], result["ends"], result["plans"])
        validate_reservations(nodes, result["jobs"], result)

    def test_fulfillment_at_R_continues_same_timestamp_dispatch(self):
        nodes = pd.DataFrame({
            "node_name": [0, 1, 2], "gpu_model": ["X", "X", "X"],
            "gpu_capacity_num": [1, 1, 1], "cpu_num": [1, 1, 0],
        })
        jobs = pd.DataFrame([
            {"job_name": 0, "gpu_model": "X", "gpu_request": 1,
             "cpu_request": 1.0, "worker_num": 1, "submit_time": 0, "duration": 10},
            {"job_name": 1, "gpu_model": "X", "gpu_request": 1,
             "cpu_request": 1.0, "worker_num": 2, "submit_time": 0, "duration": 20},
            {"job_name": 2, "gpu_model": "X", "gpu_request": 1,
             "cpu_request": 0.0, "worker_num": 1, "submit_time": 1, "duration": 5},
        ])
        nodes, jobs = prepare_data(nodes, jobs)
        result = simulate_pool(nodes, jobs, "SPT-URGENT-HOL", theta_seconds=1,
                               reservation_k=200, event_mode="shared-timer")
        self.assertEqual(result["starts"].tolist(), [0, 10, 10])
        at_r = [e for e in result["events"] if e["time"] == 10]
        self.assertEqual([e["kind"] for e in at_r],
                         ["finish", "reservation_fulfilled", "start", "start"])
        validate(nodes, result["jobs"], result["starts"], result["ends"], result["plans"])
        validate_reservations(nodes, result["jobs"], result)


if __name__ == "__main__":
    unittest.main()
