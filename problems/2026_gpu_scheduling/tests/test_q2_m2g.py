"""M2-G source-index and comparison provenance checks."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from analyze_m2g import id_hash, validate_source_index


class M2GSourceChecks(unittest.TestCase):
    def test_source_index_requires_matching_count_and_id_hash(self):
        rows = {11: {}, 12: {}}
        source = {"row_count": 2, "job_id_sha256": id_hash(set(rows))}
        self.assertEqual(validate_source_index(source, rows),
                         {"row_count_match": True, "job_id_hash_match": True})
        with self.assertRaises(ValueError):
            validate_source_index({**source, "row_count": 3}, rows)
        with self.assertRaises(ValueError):
            validate_source_index({**source, "job_id_sha256": "wrong"}, rows)

    def test_saved_full_sources_are_not_prefix_sources(self):
        path = (Path(__file__).resolve().parents[3] /
                "results/20261016-b-q2-m2g-01/comparison.json")
        comparison = json.loads(path.read_text())
        full = {item["policy"]: item for item in
                comparison["full_a10_111284"]["strategies"]}
        for item in full.values():
            source = item["timing_source"]
            self.assertEqual(source["row_count"], 111284)
            self.assertEqual(source["job_id_sha256"],
                             comparison["full_a10_111284"]["validation"]
                             [f"FULL-{item['policy']}"]["job_id_sha256"])
            self.assertIn("111284", source.get("path", source.get("member", "")))


if __name__ == "__main__":
    unittest.main()
