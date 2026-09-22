# SEARCH-BP-2.1 recursive native decoder

Stage-5 update: [simulator integration is now available](search_bp_stage5.md).
The stage-specific scope statements below record the earlier implementation phase.

Stage 4 completes Steps 5–7 on top of the audited fork BP and project-native
[Steps 1–4](search_bp_stage3.md). Root [refined.tex](../refined.tex) remains unchanged.
`_native.SearchBP2Decoder` is available for direct unit testing. **The simulator
adapter remains guarded**; simulator integration is outside this stage. No
production simulations were run.

## API and result

```python
from qec_bp_benchmark import _native

settings = _native.SearchBP2Settings()
settings.k_run = 4
settings.k_keep = 2
settings.max_cycles = 2
settings.candidate_iterations = 20
# Inherited Stage-3 fields include history_window, initial_iterations, scaling,
# selected_checks, local_variables, max_fixations and local_variable_policy.
decoder = _native.SearchBP2Decoder(
    rows=[[0, 1], [1, 2]], n=3, probabilities=[.1, .2, .3],
    observables=[[0, 2]], settings=settings,
)
result = decoder.decode([1, 1])
```

The native types are `qec::search_bp2::{DecoderSettings,Decoder,DecodeResult}`.
Settings extend Stage-3 settings with positive K_run, K_keep <= K_run, max_cycles,
and candidate_iterations >= W. Existing strict YAML fields correspond to these
budgets, but no runner wiring is added. The default local-variable policy remains
refresh_descendant; fixed_root remains available.

Model inputs are sorted unique sparse H/A rows, N columns, and finite physical
priors of shape `(N,)` in `(0,.5]`. Decode accepts only a binary original syndrome
`(number of H rows,)`. It receives no truth. The immutable model is built once;
the BP and direct OSD sessions are reused. Native settings are copied at
construction. Python settings may subsequently change without mutating a decoder.

Result fields are exactly `valid`, `correction`, `prediction`, `physical_cost`,
`osd_called`, and `correction_by_search`. Valid corrections have shape N and predictions have one bit per
A row. Invalid OSD output yields `valid=False`, empty correction/prediction and
zero cost. `osd_called` is true precisely when the direct OSD call occurred.
`correction_by_search` is true only when local combinatorial search directly
constructed the returned valid correction.
Successful BP/search results always report false. Result vectors are owned;
Python reads return copies. No cycle/beam/tree/iteration/per-phase records are
exported. Malformed inputs/settings raise `ValueError`, and overlapping/concurrent
calls on one object raise `RuntimeError` before touching session state. The guard
also resets after exceptions. Separate decoder objects can run independently.

## Cycle algorithm and deterministic policies

1. Reset physical-channel BP, execute the initial budget, and independently
   validate the full hard decision against original H/s. Return immediately on
   success. Otherwise retain B0 if it is not locally contradictory.
2. For each retained parent, construct a fresh Stage-3 posterior summary from its
   bounded trailing mean and run a fresh local search. Direct valid solutions
   return immediately. Combine all remaining candidate occurrences into **one
   global pool**, preserving each occurrence's donor BP state and full pattern.
3. Let K_s=floor(K_run/2), K_g=K_run-K_s. Take the first K_s solve-ranked
   occurrences and the first K_g guide-ranked occurrences. Deduplicate their union
   by **full resulting fixation pattern**, including ancestor zeros and ones.
   Refill from remaining guide-ranked occurrences, then solve-ranked occurrences.
   Quotas apply before deduplication, not to a pre-deduplicated pool.
4. Execute admitted candidates in solve-quota, guide-quota, guide-refill,
   solve-refill order. The **first admitted occurrence** of a duplicate pattern
   supplies its donor snapshot and delta; another parent is never silently
   substituted after selection. At most K_run descendants execute across the
   whole cycle. Fewer distinct patterns means fewer BP executions.
5. Each child inherits its own donor's free messages/posteriors and all ancestor
   fixations using the fork's strict descendant API. It starts fresh bounded
   history, receives at most candidate_iterations complete rounds, and can succeed
   before its first round. The project independently validates original H/s after
   the fork returns; the fork also checks after every round. Return immediately
   on success without running any later candidate or fallback.
6. For unsuccessful, noncontradictory instances, compute
   `R = sum_free abs(tanh(clipped_mean_llr/2)) / free_count` with no solve/guide
   component. Retain the global top K_keep by R and discard all other snapshots.
   Previous parents are replaced, never carried over just because they existed.
7. Start the next cycle with these BP states and **fresh** search objects. Stop
   after max_cycles, or when no viable parents remain. If `osd_fallback=true`,
   invoke OSD once if no earlier valid correction was returned. If false, return
   invalid immediately without OSD.

All score ties use exact binary64 comparisons, no epsilon perturbation. Admission
rankings order by the relevant ascending score, then canonical full pattern,
parent ID, delta, and pool occurrence index. Full/delta patterns are sorted
`(variable index, bit)` vectors and compare lexicographically. Parent IDs are
monotonic within a shot (B0 is 0); children receive IDs in evaluation order.
Retention orders by descending R, then full pattern and state ID. The same order
chooses the highest-R fallback state. Parent traversal uses retained order.

Deduplication removes exact patterns only. Ancestors/descendants and nearby
patterns are not treated as duplicates. No diversity heuristic, adaptive quota,
Pareto ranking, stochastic choice or cross-cycle search frontier is introduced.

## Numerical and terminal-state conventions

Both iteration budgets must cover W. Any unsuccessful **noncontradictory** BP
instance therefore has a complete trailing history. A local contradiction proves
there is no feasible correction consistent with that instance's hard fixations;
its zero-iteration/short-history state is discarded rather than assigned a
fabricated history-based R. An invalid fully fixed assignment is contradictory.
The standalone reliability helper defines an empty free mean as zero, but such
an unsuccessful state never enters retention. This resolves the corresponding
Stage-1 empty-state ambiguity without a search heuristic.

If a cycle evaluates no viable children, its old parents are discarded and
fallback uses physical channel LLRs. Remaining empty cycles would perform no work,
so they are skipped. No stale state from an earlier cycle or shot supplies OSD.

As explicitly approved during Stage 4, the highest-R retained state supplies its
**final signed posterior LLRs**, not its rolling mean. The fork represents fixed
bits by signed infinity. The project converts only these fixed entries to signed
`DBL_MAX` (positive for bit 0, negative for bit 1), since the unchanged OSD bridge
requires finite input. Free final LLRs are preserved exactly. This makes fixed
entries maximally reliable but does not turn OSD into a constrained solver; OSD
runs on original H/s and may revise fixations. With no retained state, input is
the original physical `log1p(-p)-log(p)` vector. The existing direct native
OSD-CS order-zero implementation is called exactly once, then original H/s is
validated independently. No implicit BP or higher-order OSD call is introduced.

## Work and memory bounds

Use M_s for the selected-check budget (TeX's selection M), H_c for the number of
matrix checks, N for variables, E for edges, C=max_cycles, T0 for initial BP budget
and T1 for candidate BP budget. Let

`P(m,q) = sum_{d=1..min(m,q)} binomial(m,d) 2^d`.

A satisfied probe emits at most P(m,q). A fixed_root solve tree also emits at most
P(m,q). A refresh_descendant solve tree emits at most
`min(sum_{d=1..q} m^d, P(N_free,q))`, since each expansion has at most m children,
each edge fixes at least one variable, and patterns are deduplicated per tree.
Thus a conservative common bound per selected root is
`B = max(P(m,q), sum_{d=1..q} m^d)` for refresh mode, or `B=P(m,q)` for fixed mode.
The refreshing bound cannot generally be replaced with P(m,q).

* Parent searches: at most `1 + (C-1) K_keep` (when C>=1).
* Generated candidate occurrences: at most
  `M_s B [1 + (C-1) K_keep]`; one later cycle has at most `K_keep M_s B`.
* Decimated BP executions: at most **C K_run**, never C K_run K_keep.
* Complete BP rounds: at most **T0 + C K_run T1**. Each round is
  O(E+N+H_c), including original-syndrome validation and history recording.
* Admission uses index heaps built in O(P_cycle); pops/refill cost up to
  O(P_cycle log P_cycle), with canonical pattern comparisons. Retention uses
  partial_sort over at most K_run states, O(K_run log K_keep) comparisons.
  Original matrix/scoring work is as described in Stage 3; fractional scoring
  visits all free graph edges, and guidance recomputes only touched checks.
* OSD runs at most once. Its existing sparse elimination work is separate from
  these search/BP bounds.

At most K_keep parent snapshots and K_run evaluated descendant snapshots coexist,
plus one reusable working BP session. Snapshot payload remains
`8(E+NW+2N)+N+H_c` bytes; each retained/evaluated state also owns one mean vector
and its full fixation pattern. Partial selection moves vector ownership and
immediately destroys discarded snapshots. Previous parents are then released.

Global pool entries own bounded deltas and full canonical patterns for exact
cross-parent deduplication; no BP snapshots or full residual vectors are copied
per candidate. If D is maximum current full-pattern length, cycle pattern memory
is O(P_cycle D), with D <= min(N,Cq) for descendants in cycle C. Unadmitted pool
entries, ranking heaps and search scratch are released before child BP runs;
admitted patterns die at the cycle boundary. There are no unbounded iteration
histories or saved cycle/search telemetry.

## Source and verification map

| Component | Source | Evidence |
|---|---|---|
| Pool entries, full-pattern union, dual quotas, exact dedup/refill/donor ties | `native/search_bp_admission.hpp` | independent full-sort reference, odd/even quotas, duplicates with different donors/deltas, small pools and guide-first refill |
| BP states, R, partial retention, inheritance/cycles/fallback, non-reentrant guard | `native/search_bp_decoder.hpp` | native three-cycle/multiple-parent execution assertions and independent scalar R ordering |
| Small native API | `native/search_bp_bindings.hpp` | `tests/test_search_bp_stage4.py`: independent Python controller using scalar Stage-3 tree/formulas and fork BP/OSD |
| Native tests | `tests/native/test_search_bp_stage4.cpp` | seventh Debug, sanitizer and clean-restoration target |

The production decoder has no observer/telemetry option. A private compile-time
test access point invokes the same loop with assertion callbacks in the standalone
native test only. Production uses inline no-op callbacks, stores no records, and
exports no test access point through Python. Tests inspect inherited state,
per-cycle global execution counts and fallback inputs without expanding the result.

Both new headers are in the source digest and CMake watch set. No fork source,
patch or normative TeX was changed. See STATUS.md and test_results/search_bp_stage4_*
for actual commands and results. No simulator adapter or simulation data changed.
