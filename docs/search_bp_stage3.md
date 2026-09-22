# SEARCH-BP-2.0 Steps 1–4

Stage-5 update: [simulator integration is now available](search_bp_stage5.md).
The stage-specific scope statements below record the earlier implementation phase.

Stage-4 update: [the recursive native decoder](search_bp_stage4.md) now completes
admission, retention, cycles and OSD. The partial API below remains supported;
its original stage boundary does not describe the complete native decoder.
Simulator integration remains guarded.

Normative formulas are in root [refined.tex](../refined.tex), unchanged. Stage 3
implements a native **partial service**, not an executable full decoder. The
`search_bp` runner remains guarded until admission, retained BP states, recursive
cycles and OSD fallback are implemented. No production simulation was run.

## Data flow and ownership

`qec::search_bp2::Stage3` (Python `_native.SearchBPStage3`) shares the original
immutable sparse H and physical priors with `ldpc::decimated::Session`. It owns A
once and a reusable BP session. It accepts no truth. `run_initial(syndrome,
parent_id=0)` resets the session from physical priors, runs the configured parallel
minimum-sum budget, and independently checks the full decision with original H/s.
A valid BP correction returns immediately with A times that correction. A local
contradiction returns failure without scoring nonexistent iteration history.

Otherwise the service owns one donor snapshot and one parent summary, takes the
fork's trailing clipped mean LLR, and computes c, Q, A and the ambiguity objective.
The settings require `initial_iterations >= history_window`, so every unsuccessful,
noncontradictory initial run has W completed samples. Hypothetical candidates do
not run BP. Each candidate contains only parent ID, sorted `(column, bit)` delta,
optional F_solve and F_guide. Depth is delta length; its deterministic tie key is
`(delta, parent_id)`. The full pattern is the union with the donor's fixations.

`expand_parent(snapshot, parent_id=0)` restores a copy in the worker-owned session
and expands that donor without mutating it. It validates model/prior, syndrome,
shot and numerical identity through the fork and requires a full history window.
`summarize(syndrome, fixed, mean_llr)` and `expand(parent, parent_id=0)` expose the
same Steps 2–4 for independent formula tests and future native composition.
`summarize` expects already averaged finite free LLRs of length N and sorted,
unique, binary fixed assignments. It does not average or clip them again.
`expand` accepts only summaries sharing this service's model.

The result exposes validity, initial-success flag, correction and prediction only
on success, exact fork iteration accounting, optional donor snapshot/summary,
and candidate vector. Python properties copy their arrays; C++ results own their
vectors and share const graphs. Shapes: syndrome/check arrays M, means/confidence
and masks N, corrections N, predictions number of A rows. Malformed values,
foreign states, empty/overlapping deltas and invalid settings throw
`invalid_argument` / Python `ValueError`; representational count overflow throws
`length_error`. Nonfinite score arithmetic throws `overflow_error`. A service is
worker-owned and non-reentrant; every run resets all BP state.

## Deterministic local search policies

`search.local_variable_policy` is configurable and defaults to
`refresh_descendant`, as explicitly requested during Stage 3. The native settings
use the same string field. These resolve the Stage-1 descendant-rule ambiguity;
they do not change the TeX equations.

* Both modes select all-check top-M by descending A, then check index, including
  satisfied checks. Bottom-m uses ascending parent c, then variable index.
  Undersized neighborhoods/selections use all available entries.
* Unsatisfied roots branch on their selected local set in ascending physical
  weight, then index. A child fixes earlier eligible variables to zero and its
  selected variable to one. Every zero and one counts toward q. The frontier
  expands by ascending F_solve, then canonical delta. Every generated solution is
  immediately checked against original H/s; the first valid one ends expansion.
* `fixed_root` retains the root bottom-m set throughout that tree. Descendants
  choose the lowest-index residual-unsatisfied check and intersect its neighbors
  with the root set. With no eligible local variable, that branch stops. The
  existing q <= m configuration constraint remains for this mode.
* `refresh_descendant` chooses the residual-unsatisfied check with largest
  **hypothetically updated** A (check index breaks ties), then a new bottom-m set
  of its currently free neighbors using **parent** c. Branch order is again
  physical weight/index. q bounds the whole delta along the path, and can exceed m.
* Canonical deltas are deduplicated within each anchored unsatisfied tree before
  emission/expansion. Satisfied enumeration generates each canonical delta once.
  Duplicates from different selected roots remain for future global admission;
  Stage 3 does not implement that selection policy.
* Satisfied roots enumerate all subsets of sizes 1 through min(q, local size),
  with all binary assignments, in canonical index/bit DFS order. They carry only
  F_guide. Temporary parity changes, even local contradictions, are not filtered.

For fixed-root trees and satisfied probes, per-root count is at most
`sum_{d=1..min(m,q)} choose(m,d) 2^d`. Refresh trees can leave the root set, so that
bound does **not** apply: a conservative bound is the smaller of
`sum_{d=1..q} m^d` and `N_pat(number of parent free variables,q)`. Every branch adds
at least one fixation and emits at most m children; dedup can only reduce count.
There are no extra child, leaf or node controls.

Search objects, heaps, dedup sets and scratch die after one expansion. **Search
state must not persist across future BP cycles.** After candidate BP runs and
K_keep retention, each retained BP state will start a fresh search using its new
mean/c/Q/A. The current implementation does not execute those later stages.

## Numerical equations and storage

Physical weights remain `log((1-p)/p)`, computed by the fork as
`log1p(-p)-log(p)`. Positive mean LLR favors zero. Signed tanh(mean/2), not its
absolute value, enters Q; c uses its absolute value. Fixed columns are excluded
from all free-variable products. Empty products equal one. The check denominator
is the total number of H rows, never the selected-check budget.

J_var uses the stable softplus form of the exact negative log posterior. The
hypothetical ambiguity objective keeps the **parent free-count denominator**,
sets newly fixed variable ambiguities to zero, and replaces touched check A with
1-Q-tilde. Both J_var and ambiguity gain are divided by the number of new
fixations. Empty normalized sums contribute zero. Fractional h uses **all** free
variables, including those outside the local set; empty free neighborhoods of an
unsatisfied check yield +infinity. Such generated nodes retain their guide scores
but do not expand in the solve frontier. Scores otherwise stay finite or raise an
arithmetic error; no fast-math or posterior-derived physical weights.

The parent summary is O(N+M); reusable scoring scratch is O(N+M), with a touched
check list and mask. Each delta first restores previous touched entries, XORs only
incident checks, and recomputes Q only there. Unaffected Q values are reused.
Fractional h recomputes coverage in O(E+N+M) with preallocated arrays. Candidate
storage and per-tree dedup are O(Pq); the heap stores indices, not snapshots or
residual vectors. Fixed-root pools reserve the explicit pattern bound; refresh
pools reserve the root width then grow normally. The only BP snapshot per initial
failure has the Stage-2 payload `8(E+NW+2N)+N+M` bytes. No per-candidate H or BP
state copies and no per-iteration telemetry are added.

## Implementation and tests

| Definition / responsibility | Source | Independent evidence |
|---|---|---|
| Original H/A, physical priors, settings and compact candidates | `native/search_bp_model.hpp` | malformed inputs, original-H validation, A prediction |
| c, Q, A, U; J_var, hypothetical Q, G_amb, F_guide; g/h/F_solve | `native/search_bp_scores.hpp` | scalar Python recomputes every check and every equation over exhaustive small patterns |
| Top-M, bottom-m, probes, both canonical tree policies and bounds | `native/search_bp_search.hpp` | combinatorial enumeration, 24 randomized policy/reference cases, ties, refresh leaving root, dedup |
| Fork BP / Steps 1–4 service, reset and snapshots | `native/search_bp_stage3.hpp` | rolling mean versus final posterior, donor immutability, repeated shots, early BP/search success |
| Checked Python boundary | `native/search_bp_bindings.hpp` | `tests/test_search_bp_stage3.py` |
| Standalone memory/undefined-behavior checks | `tests/native/test_search_bp_stage3.cpp` | Debug and ASan/UBSan CTest |

All five headers enter `native_sources.HYBRID_PROJECT_FILES`; CMake watches them
and the project extension includes the binding. No fork source changed in Stage 3.
The restoration test builds the new sixth native target from restored sources.
See STATUS.md and `docs/test_results/search_bp_stage3_*` for actual command results.
