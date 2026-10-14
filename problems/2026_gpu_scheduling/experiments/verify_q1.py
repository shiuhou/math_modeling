#!/usr/bin/env python3
"""Compare recomputed Q1 evidence with the audited handoff, without rescheduling."""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff-zip", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="New verification JSON")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output exists; choose a new file")
    checks = {}
    with ZipFile(args.handoff_zip) as archive:
        prefix = "Q1_final/results/"
        saved = json.loads(archive.read(prefix + "q1_results.json"))
        current = json.loads((args.results / "q1_results.json").read_text())
        if set(saved) != set(current):
            raise ValueError("Q1 JSON fields differ")
        for key in saved.keys() - {"input_sha256"}:
            a, b = saved[key], current[key]
            agrees = (math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-9)
                      if isinstance(a, (int, float)) else a == b)
            if not agrees:
                raise ValueError(f"Q1 statistic differs: {key}: {a!r} != {b!r}")
        checks["q1_statistics"] = {"status": "PASS", "fields_checked": len(saved)-1,
                                   "excluded_field": "input_sha256 (reported separately)"}
        tables = sorted(name for name in archive.namelist()
                        if name.startswith(prefix) and name.endswith(".csv"))
        if len(tables) != 9:
            raise ValueError("Expected all nine audited Q1 tables")
        for member in tables:
            name = Path(member).name
            original = archive.read(member)
            regenerated = (args.results / name).read_bytes()
            a, b = pd.read_csv(io.BytesIO(original)), pd.read_csv(io.BytesIO(regenerated))
            pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-11, atol=1e-9)
            checks[name] = {"status": "PASS", "rows": len(b), "columns": len(b.columns),
                            "byte_identical": original == regenerated,
                            "handoff_sha256": sha(original), "recomputed_sha256": sha(regenerated)}
    result = {"kind": "q1_handoff_comparison", "status": "PASS",
              "scope": "All numeric and semantic Q1 outputs; input byte provenance is separate",
              "handoff_zip_sha256": sha(args.handoff_zip.read_bytes()), "checks": checks,
              "input_provenance": {
                  "handoff": saved["input_sha256"], "current": current["input_sha256"],
                  "node_bytes": "PASS" if saved["input_sha256"]["node_info_df.csv"] == current["input_sha256"]["node_info_df.csv"] else "FAIL",
                  "historical_job_byte_identity": "BLOCKED" if saved["input_sha256"]["job_info_clean.csv"] != current["input_sha256"]["job_info_clean.csv"] else "PASS",
                  "reason": "Historical job bytes/original data ZIP are unavailable. Matching outputs do not establish byte identity; independent job-field comparison is recorded in the run manifest."}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    print("PASS: all Q1 statistics and nine handoff tables agree; byte provenance reported separately")


if __name__ == "__main__":
    main()
