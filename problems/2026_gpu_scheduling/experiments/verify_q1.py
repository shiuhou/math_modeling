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
    reference = parser.add_mutually_exclusive_group(required=True)
    reference.add_argument("--handoff-zip", type=Path, help="Optional original audited ZIP")
    reference.add_argument("--reference-dir", type=Path, help="Git-contained audited Q1 results; no attachment needed")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="New verification JSON")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output exists; choose a new file")
    checks = {}
    if args.handoff_zip:
        with ZipFile(args.handoff_zip) as archive:
            prefix = "Q1_final/results/"
            originals = {Path(n).name: archive.read(n) for n in archive.namelist()
                         if n.startswith(prefix) and (n.endswith('.csv') or n.endswith('q1_results.json'))}
    else:
        originals = {p.name: p.read_bytes() for p in args.reference_dir.iterdir()
                     if p.suffix == '.csv' or p.name == 'q1_results.json'}
    saved = json.loads(originals['q1_results.json'])
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
    tables = sorted(name for name in originals if name.endswith(".csv"))
    if len(tables) != 9:
        raise ValueError("Expected all nine audited Q1 tables")
    for member in tables:
        name = Path(member).name
        original = originals[member]
        regenerated = (args.results / name).read_bytes()
        a, b = pd.read_csv(io.BytesIO(original)), pd.read_csv(io.BytesIO(regenerated))
        pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-11, atol=1e-9)
        checks[name] = {"status": "PASS", "rows": len(b), "columns": len(b.columns),
                        "byte_identical": original == regenerated,
                        "handoff_sha256": sha(original), "recomputed_sha256": sha(regenerated)}
    result = {"kind": "q1_handoff_comparison", "status": "PASS",
              "scope": "All numeric and semantic Q1 outputs; input byte provenance is separate",
              "reference_kind": "handoff_zip" if args.handoff_zip else "git_results",
              "handoff_zip_sha256": sha(args.handoff_zip.read_bytes()) if args.handoff_zip else None, "checks": checks,
              "input_provenance": {
                  "handoff": saved["input_sha256"], "current": current["input_sha256"],
                  "node_bytes": "PASS" if saved["input_sha256"]["node_info_df.csv"] == current["input_sha256"]["node_info_df.csv"] else "FAIL",
                  "reference_job_byte_identity": "BLOCKED" if saved["input_sha256"]["job_info_clean.csv"] != current["input_sha256"]["job_info_clean.csv"] else "PASS",
                  "historical_job_byte_identity": "PASS" if args.handoff_zip and saved["input_sha256"]["job_info_clean.csv"] == current["input_sha256"]["job_info_clean.csv"] else "BLOCKED",
                  "reason": "This checks the chosen reference only. Historical original job bytes remain unavailable; agreement with Git results does not resolve the earlier handoff byte discrepancy."}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    print("PASS: all Q1 statistics and nine handoff tables agree; byte provenance reported separately")


if __name__ == "__main__":
    main()
