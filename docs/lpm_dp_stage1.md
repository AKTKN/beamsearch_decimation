# LPM-DP 1.0 Stage 1: standalone candidate generator

Stage 1 implements only the native candidate generator specified by
`local_parity_decimation_note.tex`. It does not run BP, retain a beam, call OSD,
or expose a simulator/Python decoder. The BP fork is unchanged. The explicit
`ParentView::check_to_variable` input supplies the final completed-iteration
check-to-variable messages until a later stage provides an audited snapshot API.

## Public native API

The implementation is header-only in `native/lpm_dp_model.hpp` and
`native/lpm_dp_candidates.hpp`, under `qec::lpm_dp`:

- `Settings::validate()` owns exactly the note's eight parameters and ranges.
- `summarize_parent(parent, settings)` validates immutable parent arrays, applies
  fixed values to the syndrome, detects contradictions/existing solutions,
  averages exactly `W` individually clipped history rows, and forms the top-`M`
  active uncertainty pool.
- `select_region(graph, summary, settings)` sparsely accumulates single-check and
  shared-pair weights, chooses one or two checks with the normative ties, forms
  the full free neighborhood, and fixes one nested location order.
- `build_local_fields(parent, region, settings)` forms clipped cavity fields in
  check-ID order while excluding selected-check messages. It returns each
  variable's joint parity label, unary probabilities, and stable unary costs.
- `build_dp_tables(region, fields, residual, settings)` builds all suffix
  sum-product masses, full prefix masses, and exact per-state top-`K` prefix
  lists for every nested fixation count.
- `evaluate_fixation_count(...)` exposes one `q` marginal for focused checking.
- `choose_fixation_count(parent_id, region, tables, settings)` tests `q0` down to
  one, returns the first count meeting the retained-mass target, and emits at
  most `K` canonical original-variable-ID patterns.
- `generate_candidates(parent, settings)` composes the preceding operations.

`ParentView` is a non-owning immutable view; results own their vectors. Parent
history is oldest-to-newest and must have exactly `history_window` full rows.
The edge-message vector uses the same row-edge indexing as `Graph::col` and
`Graph::row`. Free histories/messages must be finite; fixed-variable infinity
placeholders are allowed because fixed variables never enter scoring.

Normal outcomes use `Status::{Ok, ParentContradiction, ExistingSolution,
NoActiveVariables, LocalInfeasible}`. Shape, range, duplicate, non-finite, and
incomplete-region errors throw before DP work. A local parity inconsistency is a
normal `LocalInfeasible` result and does not trigger selection of another region.

## Exactness and ordering

The selected state has `S = 2^|A| <= 4` entries. A shared variable carries a
multi-bit parity label, so the two-check model is never factorized. Every variable
in `V_A \ F_q`, including variables outside the uncertainty pool, is marginalized.
The implementation stores at most `K` logical entries per prefix state, sorts the
at-most-`2K` transition work list by exact binary64 cost then selected-order word,
and sorts the at-most-`SK` terminal list by the same order. It does not enumerate
`2^q` or `2^|B_q|` assignments. The selected-order word is safely constructed and
decoded for `q=64`; returned `(variable, bit)` pairs are then sorted by variable ID
without changing candidate rank.

The normalizer uses untruncated prefix/suffix sum-product arrays. Retained mass is
therefore measured against the complete local marginal, not renormalized over the
returned list. Positive roundoff is handled only with the note's binary64 bound;
candidate comparisons have no epsilon. For `q=1`, `K>=2` retains the complete
feasible binary support and mass is set analytically to one.

## Complexity and bounded memory

With maximum variable/check degrees `d_v,d_c`, `S<=4`, pool size `M`, maximum
fixation count `q0<=64`, and list width `K`, the implementation follows the note's
safe bound

```
O(n W + n log(M+1) + M d_v^2 log(M d_v^2+2)
  + E_A + S |V_A| + S K q0 log(S K+1)).
```

There is no assignment-count exponential. Parent summarization allocates one
`m`-byte residual, one `n`-byte free mask, two `8n`-byte arrays, and a top-`M`
heap once per parent—not once per returned candidate. Excluding those parent-wide
arrays and result ownership, the derived peak live-element bound is:

```
M heap records
+ at most M d_v single contributions
+ at most M * d_v(d_v-1)/2 pair contributions
+ O(|V_A|) region/field records
+ 2(q0+1)S doubles
+ at most 2SKq0 temporary/capacity ListEntry records
+ at most SK terminal ListEntry records.
```

On the validation ABI, `ListEntry` is 16 bytes and `LocalVariable` is 48 bytes.
For the default `S=4,q0=4,K=2`, the numeric-array payload (320 bytes), embedded
per-state vector controls (480 bytes), conservative retained-list payload capacity
(1,040 bytes), and terminal-list payload (128 bytes) total 1,968 bytes. Outer
objects and allocator/node overhead for the sparse ordered maps and
`O(|V_A|)` records are additional.
Thus total generator scratch scales as `O(n+m+M d_v^2+|V_A|+SKq0)`, while each
returned candidate owns only `O(q0)` pattern data and never an `O(n)` or `O(E)`
copy. No unbounded frontier exists.

## Verification

`tests/native/test_lpm_dp.cpp` covers parameters, clipped history, fixed and
disconnected exclusions, deterministic ties, one/two-check selection, shared
variables, nested locations, cavity exclusion/clipping, one- and four-state DP,
the worked shared-boundary example, empty boundary, exact list ordering, `q=64`,
mass/count selection, fallback, local infeasibility, malformed inputs, and the
end-to-end composition. A fixed-seed independent enumerator checks 600 random
one/two-row models of up to eight variables: 576 feasible models, 24 infeasible
models, and 1,646 fixation marginals.

Final Stage-1 evidence in the `search_decimation` environment:

- focused Debug and ASan/UBSan test: passed;
- complete Debug native CTest: 8/8 passed;
- dependency audit and editable source-hashed extension rebuild: passed;
- isolated fork restoration, fresh project rebuild, identity checks and native
  CTest: 8/8 passed;
- full Python suite: 331 passed, one skipped, and one pre-existing legacy-config
  discovery failure. The failure is detailed in `STATUS.md`; no LPM-DP test failed.

## Scope and deviations

There are no algorithmic deviations from the note. Stage 1 deliberately uses an
explicit edge-aligned check-to-variable message input instead of changing the BP
fork. No recursive BP execution, warm-start application, child contradiction
filter, beam admission/retention, OSD fallback, bindings, config, or simulator
integration is present.
