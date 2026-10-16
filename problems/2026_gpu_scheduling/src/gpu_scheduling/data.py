"""Read immutable CSV bytes from a directory or the original data ZIP.

The scale of 100 is an explicit restriction of the supplied research baseline,
checked before conversion; it is not an additional competition requirement.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

CPU_SCALE = 100
DAY = 86400
FILENAMES = ("node_info_df.csv", "job_info_clean.csv")


def native(value):
    if isinstance(value, dict):
        return {str(key): native(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [native(item) for item in value]
    if isinstance(value, np.ndarray):
        return native(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


def integer_array(series, scale=1):
    values = series.to_numpy(dtype=float) * scale
    if (not np.isfinite(values).all()
            or not np.allclose(values, np.rint(values), rtol=0, atol=1e-8)
            or (np.abs(values) >= 2**63).any()):
        raise ValueError(f"{series.name}: cannot represent values at scale {scale}")
    return np.rint(values).astype(np.int64)


def prepare_data(nodes, jobs):
    """Validate and normalize copies; do not edit the source dataframes or files."""
    nodes, jobs = nodes.copy(), jobs.copy()
    required_n = {"node_name", "gpu_model", "gpu_capacity_num", "cpu_num"}
    required_j = {"job_name", "gpu_model", "cpu_request", "gpu_request",
                  "worker_num", "submit_time", "duration"}
    if not required_n <= set(nodes) or not required_j <= set(jobs):
        raise ValueError("Required columns missing")
    if nodes.empty or jobs.empty:
        raise ValueError("Empty node or job data")
    if nodes.isna().any().any() or jobs.isna().any().any():
        raise ValueError("Missing values found")
    for column in ("node_name", "gpu_capacity_num"):
        nodes[column] = integer_array(nodes[column])
    for column in ("job_name", "gpu_request", "worker_num", "submit_time", "duration"):
        jobs[column] = integer_array(jobs[column])
    if nodes.node_name.duplicated().any() or jobs.job_name.duplicated().any():
        raise ValueError("Duplicate IDs")
    # Unlike the original reader, accept fractional node CPU capacity at the
    # same checked precision as requests. Raw values remain available for metrics.
    nodes["cpu_units"] = integer_array(nodes.cpu_num, CPU_SCALE)
    jobs["cpu_units"] = integer_array(jobs.cpu_request, CPU_SCALE)
    if not (nodes.gpu_capacity_num > 0).all() or not (nodes.cpu_units >= 0).all():
        raise ValueError("Invalid capacity")
    if not (jobs[["gpu_request", "worker_num", "duration"]] > 0).all().all():
        raise ValueError("Invalid positive demand/duration")
    if not (jobs[["cpu_units", "submit_time"]] >= 0).all().all():
        raise ValueError("Invalid CPU demand or arrival time")
    if not set(jobs.gpu_model) <= set(nodes.gpu_model):
        raise ValueError("Unknown GPU type")
    nodes = nodes.sort_values("node_name", kind="stable").reset_index(drop=True)
    jobs = jobs.sort_values(["submit_time", "job_name"], kind="stable").reset_index(drop=True)
    return nodes, jobs


def read_data(path: Path):
    """Return validated nodes, jobs and hashes of the actual input bytes."""
    path = Path(path)
    if path.is_dir():
        contents = {name: (path / name).read_bytes() for name in FILENAMES}
    else:
        with ZipFile(path) as archive:
            contents = {}
            for name in FILENAMES:
                matches = [entry for entry in archive.infolist()
                           if Path(entry.filename).name == name
                           and not entry.filename.startswith("__MACOSX/")]
                if len(matches) != 1:
                    raise ValueError(f"Expected one {name}, found {len(matches)}")
                contents[name] = archive.read(matches[0])
    nodes, jobs = prepare_data(*(pd.read_csv(io.BytesIO(contents[name])) for name in FILENAMES))
    hashes = {name: hashlib.sha256(blob).hexdigest() for name, blob in contents.items()}
    return nodes, jobs, hashes
