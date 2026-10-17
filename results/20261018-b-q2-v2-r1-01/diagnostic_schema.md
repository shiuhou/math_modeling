# Diagnostic interpretation schema R1 (no counter or scheduler change)

Scope: d29d895 / simulate_pool, one GPU pool per call. These definitions correct the
interpretation of the 20261017 aggregates; all original numbers remain unchanged.

| Field | Unit and scope | Reset | diagnostics=False |
|---|---|---|---|
| dispatch_timestamps | dispatch() calls, despite its historical name | pool invocation | still counted |
| order_builds | executions of _ordered; excludes plain HOL heap/deque path | pool invocation | still counted |
| candidate_attempts / bypass_candidate_checks | bypass attempts, successes and failures; prefix and protected checks exempt | aggregate per pool; K budget per dispatch epoch | still counted |
| unique_candidate_ids | distinct job indices ever attempted as bypass candidates in this pool run | pool invocation, never at timestamp | null, not zero |
| repeated_candidate_attempts | attempts whose ID already appeared anywhere earlier in this run | pool invocation | null, not zero |
| budget_exhausted | emissions of budget_exhausted event | pool invocation | still counted |
| current_plan_evaluations | current-resource cache misses invoking FF planner; excludes future planners | pool invocation | still counted |
| current_plan_cache_hits | current-resource cache lookups served without planner computation | pool invocation | still counted |

Thus attempts = run-wide unique IDs + run-wide repeated attempts when enabled.
Repeated attempts include different timestamps and changed resource states. They
are not a measure of wasted computation or a causal fraction of waiting.
Same-timestamp unique/repeated bypass attempts: NOT_AVAILABLE in the saved evidence.
The event ledger has no per-candidate attempt record, so aggregates cannot recover them.

The current top-level event loop dispatches once after batching each epoch; this
explains equality of call count and epoch count in this implementation. No separately
measured unique-dispatch-timestamp field was persisted. Do not equate order_builds,
dispatch calls and unique timestamps as metric definitions (ordinary HOL has zero
order_builds). diagnostics=False disables only ID sets, not other cost counters/events.

Cost semantics: child_wall_seconds is wrapper-observed child wall time;
runtime_seconds is the policy loop interval, not child wall; scheduler_seconds
includes simulate_pool's internal capacity check; validation_seconds is subsequent
reservation replay; io_seconds also includes schedule hashing after persistence.
These are elapsed times, not measured process CPU times. CPU time: NOT_AVAILABLE.

Errata: the original notes labelled runtime_seconds as wall, rounded 65k cost as
2.8x, and understated the full candidate mean difference. R1 tables are generated
from exact JSON and distinguish child wall. No old manifest is edited. The old
manifest's code.commit points at an amended-away intermediate commit, and its
analysis timing is not a measurement. Use each preserved child summary's actual
run commit/dirty/source hashes and the existing d29d895 source tree for provenance.
Independent validation in these runs was in-process over the in-memory result;
a separate persisted replay report was not found. Its status is MISSING, not PASS.
