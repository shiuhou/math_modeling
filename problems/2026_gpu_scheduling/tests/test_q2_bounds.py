import copy
import itertools
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from analyze_m2f_bounds import (
    brute_q,
    count_lower_bound,
    decompose,
    validate_against_raw,
)


def timing(job_name, submit, duration, workers=1, gpu=1, start=None):
    start = submit if start is None else start
    return {
        "job_name": job_name,
        "gpu_model": "A10",
        "submit_time": submit,
        "duration": duration,
        "worker_num": workers,
        "gpu_request": gpu,
        "cpu_units": 100,
        "start": start,
        "finish": start + duration,
    }


def exhaustive_q(widths, capacity):
    best = 0
    widths = list(widths)
    for mask in range(1 << len(widths)):
        kept = [widths[i] for i in range(len(widths)) if mask & (1 << i)]
        if sum(kept) <= capacity:
            best = max(best, len(kept))
    return len(widths) - best


class M2FBoundChecks(unittest.TestCase):
    def test_zero_overload(self):
        rows = [timing(0, 0, 5), timing(1, 2, 3)]
        result = count_lower_bound(rows, 2)
        self.assertEqual(result["integral_q_job_seconds"], 0)
        self.assertEqual(result["peak_q_jobs"], 0)

    def test_three_same_gpu_jobs_and_half_open_endpoints(self):
        rows = [timing(i, 0, 10) for i in range(3)]
        result = count_lower_bound(rows, 1)
        self.assertEqual(result["integral_q_job_seconds"], 20)
        self.assertEqual(result["q_positive_seconds"], 10)
        # At t=10 all three jobs leave Z(t); no extra tail is integrated.
        self.assertEqual(result["integral_end_seconds"], 10)

    def test_width_histogram_minimum_deletions_is_not_rounding(self):
        rows = [timing(0, 0, 4, gpu=2), timing(1, 0, 4, gpu=2),
                timing(2, 0, 4, gpu=2)]
        result = count_lower_bound(rows, 4)
        self.assertEqual(result["peak_q_jobs"], 1)
        self.assertEqual(result["integral_q_job_seconds"], 4)
        self.assertEqual(brute_q([2, 2, 2], 4), 1)
        self.assertNotEqual(3 - (6 // 4), 1)

    def test_gang_width_and_random_small_oracle(self):
        rows = [timing(0, 0, 2, workers=2), timing(1, 0, 2, workers=1)]
        self.assertEqual(count_lower_bound(rows, 2)["peak_q_jobs"], 1)
        for widths in itertools.product((1, 2, 3), repeat=4):
            rows = [timing(i, 0, 1, gpu=w) for i, w in enumerate(widths)]
            result = count_lower_bound(rows, 4)
            self.assertEqual(result["peak_q_jobs"], exhaustive_q(widths, 4))

    def test_exact_decomposition_beyond_and_positive_gap(self):
        rows = [timing(0, 0, 2, start=0), timing(1, 0, 2, start=5)]
        # q=1 for [0,2), while the second job waits five seconds.
        lower = count_lower_bound(rows, 1)["integral_q_job_seconds"]
        result = decompose(rows, lower, expected_mean_hours=sum((0, 5)) / (2 * 3600))
        self.assertEqual(result["capacity_lower_bound_job_seconds"], 2)
        self.assertEqual(result["within_window_gap_job_seconds"], 0)
        self.assertEqual(result["beyond_duration_wait_job_seconds"], 3)
        self.assertEqual(result["residual_job_seconds"], 0)

        rows = [timing(0, 0, 20, start=0), timing(1, 0, 20, start=10),
                timing(2, 0, 20, start=20)]
        lower = count_lower_bound(rows, 2)["integral_q_job_seconds"]
        result = decompose(rows, lower, expected_mean_hours=30 / (3 * 3600))
        self.assertEqual(result["within_window_gap_job_seconds"], 10)
        self.assertEqual(result["beyond_duration_wait_job_seconds"], 0)

    def test_input_set_mismatch_is_not_silently_comparable(self):
        rows = [timing(0, 0, 1), timing(1, 0, 1)]
        altered = copy.deepcopy(rows)
        altered[1]["job_name"] = 99
        raw = pd.DataFrame({
            "job_name": [0, 1], "gpu_model": ["A10", "A10"],
            "submit_time": [0, 0], "duration": [1, 1],
            "worker_num": [1, 1], "gpu_request": [1, 1],
            "cpu_units": [100, 100],
        })
        with self.assertRaises(ValueError):
            validate_against_raw(altered, raw)

        changed = copy.deepcopy(rows)
        changed[1]["duration"] = 9
        with self.assertRaises(ValueError):
            validate_against_raw(changed, raw)


if __name__ == "__main__":
    unittest.main()
