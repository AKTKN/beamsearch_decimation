# search_bp algorithm specification (SEARCH-BP-1.0)

`search_bp` combines the persistent best-first correction search with a retained
beam of stateful parallel min-sum BP candidates and direct native OSD-CS0 fallback.
All ordering is deterministic and all costs use the original physical channel
weights.

## Cycle contract

For each of `search.max_cycles` cycles, the search expands at most the scalar
`search.expansions_per_cycle` nodes. There is no independent total-expansion
or generated-node limit. The expanded-node bound is therefore
`max_cycles * expansions_per_cycle`; the finite Tanner graph determines how many
children each expanded node constructs. The best unused search patterns, up to
`bp.beam_width`, are admitted into the candidate pool. Retained candidates are
also revisited, and deterministic ranking keeps at most `bp.beam_width` states
for the next cycle.

Each visited candidate requests exactly `bp.max_iteration` new parallel min-sum
iterations, stopping early only on convergence or the optional prefix CPU bound.
There is no admissions option and no shot-wide total-iteration cap. A retained
candidate continues its own messages. With `retained_ancestor`, a fresh strict
descendant inherits the active variable-to-check messages of its nearest retained
ancestor; `cold` reconstructs every visit from physical priors.

## Hard decimation

A search pattern is a sorted partial assignment with values 0 or 1. For a
candidate pattern `F`, BP constructs the induced Tanner graph on variables not in
`F`: every edge incident to a fixed variable is excluded from both check and
variable updates. Starting from the measured syndrome `s`, every fixed-one column
is XORed into the residual syndrome; fixed-zero columns do not change it. Empty
residual checks with value one are local contradictions.

The BP hard decision for every free variable and all numerical behavior are those
of the native min-sum kernel; `search_bp` exposes neither an LLR clip nor a
hard-decision-at-zero option. Fixed values are restored into the complete
correction before validation, physical-cost scoring, logical prediction, beam
ranking, and solution comparison. Thus fixed nodes are removed from BP message
passing but never removed from objective or correctness evaluation.

## Termination and fallback

Search solutions and BP solutions are always checked against the original `H`
and syndrome. `first_valid` returns the first validated solution;
`bounded_improve` retains the lowest physical-cost solution with deterministic
bit-vector tie breaking for the configured post-solution cycles. If no solution
is retained, direct native OSD-CS0 uses either physical channel LLRs or the best
retained candidate's reconstructed full-vector LLRs. OSD output is again checked
against the original model.

The active configuration identity is `kind: search_bp`, `profile: search_bp`,
`algorithm_version: SEARCH-BP-1.0`. The typed data contract is
`search_bp_parquet/2` in `search_bp_parquet_schema.json`.
