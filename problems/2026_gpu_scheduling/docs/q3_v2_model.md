# Q3-V2 bounded substitution model

Q3-V2 keeps the V1 physical model fixed: 224,112 original jobs, 60 dedicated
A100-SXM4-80GB donor nodes, the remaining 372 A100 nodes for native A100
jobs, unchanged worker CPU/GPU requests, same-node gang placement, no
preemption or migration, and complete-drain timing at `H=7,776,000` seconds.
`M0` is model isolation. `R0` is V1's 10% SHA-256 policy with namespace
`q3-fixed-split-v1`; sigma is a scenario assumption rather than a benchmark.

## Candidate A: R-shape

The policy first applies exactly the V1 eligibility and hash threshold. Let

\[
 \rho_j = \frac{c_j}{g_j}, \qquad
 \bar\rho_B = \frac{\sum_{i\in B} C_i^{cap}}{\sum_{i\in B} G_i^{cap} }.
\]

An eligible, hash-selected A10 job is routed only when
`rho_j <= rho_bar_B`. The threshold is derived from the 60 selected rows of
`node_info_df.csv`, not from hardware convention. The data give 128 CPU and 8
GPU per donor node, hence `rho_bar_B = 16 CPU/GPU`. Jobs that fail the shape
rule remain in the native A10 partition with their original duration. This
changes both the routed set and its CPU/GPU work, so an R-shape result cannot
be interpreted as a pure CPU-ratio causal effect. It also does not choose an
optimal top-N subset or use future waits.

For each policy and sigma, R-shape is compared with R0 at the same sigma and
with M0. The primary outcomes are original-A10 and all-job JCT, relative
completion delay, 90-day completion count, waiting tails, positive completion
delay, zero-wait newly delayed jobs, and short/long × single/multi-worker
strata. Native A100 timing and node placement are required to match R0 exactly
for the same hard partition; otherwise the run is rejected as a coupling or
implementation error.

## Candidate B: completion-cost routing (deferred)

The intended rule for an R-shape-eligible arrival is

\[
 \hat s_A - \hat s_B > (\sigma-1)p_j + \eta,
 \qquad \eta=0.
\]

The estimates may use only the current time, already arrived waiting jobs,
currently running jobs with known remaining duration, and current CPU/GPU
state. They may not use future submissions, post-hoc M0 waiting, or a future
realized completion time. Same-time arrivals are processed by ascending
original job ID and every decision must update the shadow state.

The current `q3.route()` constructs a complete route before calling the DES;
it has no safe arrival callback. A minimal future interface is
`route_on_arrival(state, job) -> (route_reason, effective_duration,
updated_shadow_state)`, where `state` contains current time, arrived queue,
running remaining durations, free resources, and both partition queue states.
Until a small callback implementation is proven against event ordering and
information-boundary tests, Candidate B remains `IMPLEMENTATION_DEFERRED` and
no full-trace B numbers are reported. A minimal scalar example is: with
`p_j=10`, `sigma=2`, `eta=0`, `s_hat_A=200`, and `s_hat_B=150`, the strict
test `50 > 10` routes; with `s_hat_A=160` it does not route because the test
is not strict. A same-time second job must see the first job's updated shadow
state. These examples specify the rule only; they are not performance data.
