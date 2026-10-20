"""Second-round Q3 candidates built on the frozen V1 DES.

Only the R-shape candidate is executable here.  It reuses V1 eligibility,
hashing, physical partitions, and ``simulate_pool``; it adds one declared
resource-shape filter before the same foreign partition.  The completion-cost
candidate is intentionally specified but not implemented because the current
V1 entry point decides the complete route before the DES sees any arrivals.
"""
from __future__ import annotations

import math

import pandas as pd

from .q3 import Config, FOREIGN, SOURCE, TARGET, route
from .simulator import simulate_pool

CPU_SCALE = 100
R_SHAPE = "R-shape"


def derive_shape_limit(nodes: pd.DataFrame, donor_nodes: int) -> float:
    """Derive CPU/GPU capacity ratio from the selected physical donor nodes."""
    target = nodes[nodes.gpu_model == TARGET].sort_values("node_name")
    if donor_nodes <= 0 or donor_nodes >= len(target):
        raise ValueError("R-shape requires a nonempty native A100 pool")
    donor = target.head(donor_nodes)
    ratios = donor.cpu_units.to_numpy(dtype=float) / CPU_SCALE / donor.gpu_capacity_num.to_numpy(dtype=float)
    if not (ratios == ratios[0]).all():
        raise ValueError("R-shape threshold is ambiguous for heterogeneous donor nodes")
    if not math.isfinite(float(ratios[0])) or ratios[0] <= 0:
        raise ValueError("Invalid derived donor CPU/GPU ratio")
    return float(ratios[0])


def shape_allowed(row, limit: float) -> bool:
    """Return the declared per-worker CPU/GPU shape condition."""
    ratio = float(row.cpu_units) / CPU_SCALE / float(row.gpu_request)
    return ratio <= float(limit) + 1e-12


def route_shape(nodes: pd.DataFrame, jobs: pd.DataFrame, config: Config):
    """Apply V1 eligibility/hash, then reject only over-shaped routed A10 jobs."""
    pools, frame = route(nodes, jobs, config)
    limit = derive_shape_limit(nodes, config.donor_nodes)
    original_a10 = frame.original_gpu_model == SOURCE
    rejected = original_a10 & (frame.route_reason == "routed") & ~frame.apply(
        lambda row: shape_allowed(row, limit), axis=1
    )
    if rejected.any():
        indices = frame.index[rejected]
        frame.loc[indices, "gpu_model"] = SOURCE
        frame.loc[indices, "duration"] = frame.loc[indices, "original_duration"]
        frame.loc[indices, "partition"] = SOURCE
        frame.loc[indices, "route_reason"] = "shape_rejected"
    frame.attrs["shape_limit_cpu_per_gpu"] = limit
    frame.attrs["shape_candidate"] = R_SHAPE
    # V1 already checked every empty-pool demand.  Reverting a routed row to
    # its native pool cannot make either pool less feasible.
    return pools, frame


def simulate_shape(nodes: pd.DataFrame, jobs: pd.DataFrame, policy: str, config: Config):
    """Run the unchanged pool DES after R-shape routing."""
    pools, routed = route_shape(nodes, jobs, config)
    frames, ledger = [], []
    for key, sub in routed.groupby("partition", sort=True):
        pool = pools[key].sort_values("node_name").reset_index(drop=True)
        result = simulate_pool(pool, sub, policy)
        frame = result["jobs"].copy()
        frame["start"], frame["finish"] = result["starts"], result["ends"]
        frames.append(frame)
        for jid, plan in zip(frame.job_name, result["plans"]):
            ledger.extend((int(jid), int(pool.node_name.iloc[i]), int(w)) for i, w in plan)
    out = pd.concat(frames, ignore_index=True).sort_values("job_name").reset_index(drop=True)
    out.attrs.update(routed.attrs)
    return out, pd.DataFrame(ledger, columns=["job_name", "node_name", "workers"]).sort_values(
        ["job_name", "node_name"]
    ).reset_index(drop=True)


def completion_cost_spec():
    """Machine-readable specification for the deferred online candidate."""
    return {
        "status": "IMPLEMENTATION_DEFERRED",
        "candidate": "completion-cost",
        "eligibility": "R-shape eligible jobs only",
        "decision": "s_hat_A - s_hat_B > (sigma - 1) * p_j + eta",
        "eta_seconds": 0,
        "allowed_information": [
            "arrived jobs",
            "currently running fixed-configuration jobs",
            "known remaining durations and current resources",
        ],
        "forbidden_information": [
            "future submissions",
            "post-hoc M0 waiting",
            "future realized completion time of the candidate",
        ],
        "minimum_interface": {
            "name": "route_on_arrival(state, job)",
            "state": ["now", "arrived_waiting_jobs", "running_remaining", "free_cpu_gpu", "partition_queue_state"],
            "return": ["route_reason", "effective_duration", "updated_shadow_state"],
            "ordering": "same-submit jobs use ascending original job ID; each decision updates shadow state",
        },
        "limitation": "q3.route currently constructs the complete route before simulate_pool; no safe online callback exists yet",
    }
