"""Pure node-level placement primitives used by the single DES."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

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
