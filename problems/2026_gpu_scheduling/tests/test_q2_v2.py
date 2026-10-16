"""Small correctness contract for the SPT-HEAD-TIME candidate and diagnostics."""
import copy
import unittest

import pandas as pd

from gpu_scheduling.simulator import simulate_pool
from gpu_scheduling.validation import validate_reservations


def _nodes(gpu=(1, 1), cpu=(100, 100)):
    return pd.DataFrame({"node_name": list(range(len(gpu))), "gpu_model": ["X"] * len(gpu),
                         "gpu_capacity_num": list(gpu), "cpu_units": list(cpu)})


class HeadTimeChecks(unittest.TestCase):
    def test_cpu_limited_multworker_and_finish_equal_R(self):
        # H needs both workers and is CPU limited.  B finishes exactly at the
        # protected R and therefore remains an admissible TIME backfill.
        jobs = pd.DataFrame({"job_name": [0, 1, 2], "gpu_model": ["X"] * 3,
            "gpu_request": [1, 1, 1], "cpu_units": [100, 100, 100],
            "worker_num": [1, 2, 1], "submit_time": [0, 1, 1],
            "duration": [10, 1, 9]})
        result = simulate_pool(_nodes(), jobs, "SPT-HEAD-TIME", theta_seconds=604800,
                                reservation_k=1, event_mode="shared-timer")
        self.assertEqual(result["starts"].tolist(), [0, 10, 1])
        self.assertEqual(result["reservations"][0]["promised_R"], 10)
        self.assertIn(2, result["reservations"][0]["accepted_backfill_ids"])
        validate_reservations(_nodes(), result["jobs"], result)

    def test_promise_is_not_revoked_by_short_arrival_and_k_not_reset(self):
        jobs = pd.DataFrame({"job_name": [0, 1, 2, 3], "gpu_model": ["X"] * 4,
            "gpu_request": [1] * 4, "cpu_units": [100] * 4,
            "worker_num": [1, 2, 1, 1], "submit_time": [0, 1, 1, 2],
            "duration": [10, 1, 2, 2]})
        result = simulate_pool(_nodes(), jobs, "SPT-HEAD-TIME", theta_seconds=604800,
                                reservation_k=1, event_mode="shared-timer")
        promise = result["reservations"][0]
        self.assertEqual(promise["protected_job_name"], 1)
        self.assertEqual(promise["promised_R"], 10)
        self.assertEqual(result["starts"][1], 10)
        self.assertGreaterEqual(result["cost"]["dispatch_timestamps"], 1)
        validate_reservations(_nodes(), result["jobs"], result)
        bad = copy.deepcopy(result)
        bad["reservations"][0]["promised_R"] = 11
        with self.assertRaises(AssertionError):
            validate_reservations(_nodes(), bad["jobs"], bad)

    def test_diagnostics_do_not_change_schedule(self):
        jobs = pd.DataFrame({"job_name": [0, 1, 2], "gpu_model": ["X"] * 3,
            "gpu_request": [1] * 3, "cpu_units": [100] * 3,
            "worker_num": [1, 2, 1], "submit_time": [0, 1, 1],
            "duration": [10, 1, 2]})
        on = simulate_pool(_nodes(), jobs, "SPT-FILL", diagnostics=True)
        off = simulate_pool(_nodes(), jobs, "SPT-FILL", diagnostics=False)
        self.assertEqual(on["starts"].tolist(), off["starts"].tolist())
        self.assertEqual(on["ends"].tolist(), off["ends"].tolist())
        self.assertEqual(on["plans"], off["plans"])
        self.assertEqual(on["events"], off["events"])
        self.assertIsNone(off["cost"]["unique_candidate_ids"])


if __name__ == "__main__":
    unittest.main()
