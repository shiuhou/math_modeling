"""Pure node-level placement primitives used by the single DES."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from functools import cmp_to_key

import numpy as np


@dataclass(frozen=True)
class PlacementPlan:
    """A complete gang placement, without mutating resource state."""

    nodes: tuple[tuple[int, int], ...]
    workers: int


def slots(free_g: np.ndarray, free_c: np.ndarray, q: int, c: int) -> np.ndarray:
    """Return the number of identical workers each node can host."""
    if q <= 0 or c < 0:
        raise ValueError("worker GPU demand must be positive and CPU demand nonnegative")
    h = np.asarray(free_g, dtype=np.int64) // q
    if c:
        h = np.minimum(h, np.asarray(free_c, dtype=np.int64) // c)
    return h


def plan_first_fit(
    free_g: np.ndarray,
    free_c: np.ndarray,
    q: int,
    c: int,
    workers: int,
    order: Iterable[int] | None = None,
) -> PlacementPlan | None:
    """Construct a complete plan or return ``None`` without changing inputs."""
    if workers <= 0:
        raise ValueError("worker count must be positive")
    capacity = slots(free_g, free_c, q, c)
    if int(capacity.sum()) < workers:
        return None
    indices = list(range(len(capacity))) if order is None else list(order)
    chosen: list[tuple[int, int]] = []
    remaining = int(workers)
    for node in indices:
        room = int(capacity[node])
        if room <= 0:
            continue
        take = min(remaining, room)
        chosen.append((int(node), take))
        remaining -= take
        if remaining == 0:
            return PlacementPlan(tuple(chosen), int(workers))
    raise AssertionError("slot capacity and placement construction disagree")


def _ratio_cmp(a: int, b: int, cpu_cap: np.ndarray, gpu_cap: np.ndarray) -> int:
    """Compare only original CPU/GPU ratios exactly; ties return zero."""
    left = int(cpu_cap[a]) * int(gpu_cap[b])
    right = int(cpu_cap[b]) * int(gpu_cap[a])
    return (left > right) - (left < right)


def plan_ratio_matching(
    free_g: np.ndarray,
    free_c: np.ndarray,
    q: int,
    c: int,
    workers: int,
    *,
    capacity_g: np.ndarray | None = None,
    capacity_c: np.ndarray | None = None,
    order: Iterable[int] | None = None,
) -> PlacementPlan | None:
    """Place a complete gang, preferring nodes whose original shape fits.

    The ratio is a sorting heuristic only.  Feasibility always comes from the
    current integer worker-slot count, so a low-ratio node remains a valid
    fallback when it can host workers. All comparisons use Python integer
    cross-products. Arrays MUST be sorted by numeric node_name; order is a
    permutation of those indices, not a physical reordering of the arrays.
    """
    if workers <= 0:
        raise ValueError("worker count must be positive")
    capacity = slots(free_g, free_c, q, c)
    if int(capacity.sum()) < workers:
        return None
    original_g = np.asarray(free_g if capacity_g is None else capacity_g, dtype=np.int64)
    original_c = np.asarray(free_c if capacity_c is None else capacity_c, dtype=np.int64)
    indices = list(range(len(capacity))) if order is None else list(order)
    indices = [int(i) for i in indices if int(capacity[int(i)]) > 0]
    # Preserve node-name/index tie breaking while allowing an explicit physical
    # order for the ordinary FF sensitivity control.
    def shape_cmp(a: int, b: int) -> int:
        # R_i >= rho_j iff C_i*q >= c*G_i.  Within each group sort the
        # distance from rho exactly, then fall back to the stable node order.
        da = int(original_c[a]) * int(q) - int(c) * int(original_g[a])
        db = int(original_c[b]) * int(q) - int(c) * int(original_g[b])
        if (da >= 0) != (db >= 0):
            return -1 if da >= 0 else 1
        if da >= 0:
            # Compare (R-rho) = da/(G*q), not the raw cross-product.
            left = da * int(original_g[b])
            right = db * int(original_g[a])
            return (left > right) - (left < right) or ((a > b) - (a < b))
        return _ratio_cmp(b, a, original_c, original_g) or ((a > b) - (a < b))
    candidates = sorted(indices, key=cmp_to_key(shape_cmp))
    chosen: list[tuple[int, int]] = []
    remaining = int(workers)
    for node in candidates:
        take = min(remaining, int(capacity[node]))
        chosen.append((node, take))
        remaining -= take
        if remaining == 0:
            return PlacementPlan(tuple(chosen), int(workers))
    raise AssertionError("slot capacity and placement construction disagree")


def check_plan(
    free_g: np.ndarray,
    free_c: np.ndarray,
    q: int,
    c: int,
    plan: PlacementPlan | Iterable[tuple[int, int]],
    workers: int,
) -> None:
    """Independently check a plan against one immutable resource snapshot."""
    entries = tuple(plan.nodes if isinstance(plan, PlacementPlan) else plan)
    if sum(int(count) for _, count in entries) != int(workers):
        raise ValueError("placement does not contain exactly all workers")
    seen: set[int] = set()
    for node, count in entries:
        if node in seen or not 0 <= int(node) < len(free_g) or int(count) <= 0:
            raise ValueError("invalid or duplicate placement node")
        seen.add(int(node))
        if int(count) * int(q) > int(free_g[node]):
            raise ValueError("GPU capacity exceeded by placement")
        if int(count) * int(c) > int(free_c[node]):
            raise ValueError("CPU capacity exceeded by placement")


def apply_plan(
    free_g: np.ndarray,
    free_c: np.ndarray,
    q: int,
    c: int,
    plan: PlacementPlan | Iterable[tuple[int, int]],
    sign: int = -1,
) -> None:
    """Apply a previously checked plan atomically to both resource arrays."""
    entries = tuple(plan.nodes if isinstance(plan, PlacementPlan) else plan)
    if sign not in (-1, 1):
        raise ValueError("plan sign must be -1 or +1")
    delta_g = np.zeros_like(free_g)
    delta_c = np.zeros_like(free_c)
    for node, count in entries:
        delta_g[int(node)] += int(count) * int(q)
        delta_c[int(node)] += int(count) * int(c)
    if sign < 0 and (np.any(delta_g > free_g) or np.any(delta_c > free_c)):
        raise ValueError("plan cannot be committed to current resources")
    free_g[:] = free_g + sign * delta_g
    free_c[:] = free_c + sign * delta_c
