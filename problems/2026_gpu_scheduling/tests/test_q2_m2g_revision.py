"""Regression checks for the read-only M2-G cross-review reconciliation."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from analyze_m2g_revision import weighted_metrics


class M2GRevisionChecks(unittest.TestCase):
    def test_saved_source_counts_and_id_hashes_are_pass(self):
        root = Path(__file__).resolve().parents[3]
        result = json.loads((root / "results/20261016-b-q2-m2g-revision-01/revision.json").read_text())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["data"]["a10_jobs"], 111284)
        self.assertEqual(result["checks"]["q2_g2_vs_q3_m0_sjf_hol_a10"]["status"], "PASS")
        self.assertTrue(result["checks"]["q2_g2_vs_q3_m0_sjf_hol_a10"]["timing_rows_equal"])
        for key in ("fcfs_a10_input_match", "sjf_hol_a10_input_match",
                    "q2_g2_input_match", "q2_g3_input_match"):
            self.assertEqual(result["checks"][key]["status"], "PASS")

    def test_gpu_work_weight_is_distinct_from_job_mean(self):
        rows = {
            1: {"worker_num": 1, "gpu_request": 1, "duration": 10, "wait": 0},
            2: {"worker_num": 2, "gpu_request": 2, "duration": 10, "wait": 10},
        }
        metrics = weighted_metrics(rows)
        self.assertEqual(metrics["mean_wait_hours"], 10 / 2 / 3600)
        self.assertEqual(metrics["gpu_work_weighted_mean_wait_hours"], 40 * 10 / 50 / 3600)

    def test_budget_ratio_is_labeled_as_attempt_diagnostic(self):
        root = Path(__file__).resolve().parents[3]
        result = json.loads((root / "results/20261016-b-q2-m2g-revision-01/revision.json").read_text())
        diagnostic = result["fill_budget_diagnostic"]
        self.assertEqual(diagnostic["order_builds"], 314756)
        self.assertAlmostEqual(diagnostic["ratio_budget_exhausted_per_order_build"], 307844 / 314756)
        self.assertIn("not a fraction of waiting time", diagnostic["interpretation"])


if __name__ == "__main__":
    unittest.main()
