# SEARCH-BP-2.0 implementation map (architecture stage)

Normative algorithm: root [refined.tex](../refined.tex), section
`sec:search_guided_recursive_bp`. Its bytes and equations are unchanged. This
document maps definitions; it does not replace them. No SEARCH-BP-2.0 decoding
behavior is implemented. Public kind/profile/name remain `search_bp`, with required
`algorithm_version: SEARCH-BP-2.0` and strict `search_bp_config/3`.
Execution fails before native loading or run creation. Validation remains usable.

## Proposed source ownership

| Location (future unless stated otherwise) | Responsibility |
|---|---|
| `external_lib/ldpc/src_cpp/decimated_bp.hpp` | BP numerical/message kernel, structural fixation, bounded posterior history and owned snapshots only |
| `external_lib/ldpc/src_cpp/osd0_bridge.hpp` (existing) | Direct OSD-CS order-zero service on original H and syndrome, no implicit BP |
| `src/qec_bp_benchmark/native/search_bp/model.hpp` | Immutable original H/A, physical priors, canonical assignments; reuse generic hybrid graph/model where compatible |
| `native/search_bp/reliability.hpp` | Clipped time average, confidence, check ambiguity and BP-state reliability |
| `native/search_bp/local_search.hpp` | Local restriction, canonical branching, candidate generation, solve/guide scores |
| `native/search_bp/admission.hpp` | Global dual-score admission, deduplication and guide-first refill |
| `native/search_bp/decoder.hpp` | Initial BP, recursive cycles, retention, validation and fallback orchestration |
| `native/search_bp/bindings.hpp` | Checked thin C++17 binding; no search or iteration loops in Python |
| `config.py`, `decoders/__init__.py` (existing) | Strict configuration and truth-free adapter, presently guarded |
| `runner/`, `storage/minimal.py`, `analysis/simple_search_bp.py` (existing) | Paired simulator integration, five-field writer and direct reader |

All `native/` paths above are relative to `src/qec_bp_benchmark/`. Future project
headers must enter CMake and `native_sources.py` source hashes. Fork changes must
enter the opt-in source inventory, patch, audit and restoration tests. Neither
the historical project-local masked min-sum nor a replacement numerical kernel
may be compiled as the new decoder. No fast-math, custom allocator or SIMD work.

## Step-to-definition map

For unlabeled equations the exact TeX subsection and left-hand symbol below are
the locator; do not replace those definitions with historical SEARCH-BP-1.0 rules.

| Step | Component and exact TeX definitions |
|---|---|
| Problem | `model.hpp`: subsection `問題設定と記法`, equations H, s, V, C, physical weight w_j, N(a), D_B, U_B and residual s_a^(B). Preserve original H/A; physical weights never become posterior weights. |
| 1: initial BP | `decoder.hpp` calls fork BP with empty fixation. `Step 1: Initial BP`, equation H e-hat = s and immediate valid exit. Kernel method is unresolved below. |
| 2: time average | `reliability.hpp` consumes fork history. `eq:average_llr` is clip-per-iteration then average, not clipping the average or changing the kernel. `eq:variable_confidence` defines c_j. |
| 3: check ambiguity | `reliability.hpp`: `eq:check_probability`, `eq:check_ambiguity`; Step 3's unlabeled C_B^(M) TopM equation selects from **all** checks, including residual-satisfied checks. The preceding LLR convention and expectation equations set the signs. |
| 4: bounded search | `local_search.hpp`: `eq:local_variables`; `Local variable restriction` equation N_pat(m,q). `Search node` defines Delta D_u, D_u and `eq:node_residual`. Unsatisfied-check subsection defines g(u), R(u), k_j(u), `eq:fractional_heuristic` and `eq:fsolve`. Initial branches use physical weight then index. Satisfied-check probes enumerate patterns of depths 1 through q and have only a guide score. No extra child/leaf cap. |
| 4: guidance | Same component: `Guide score` equation P_B(x_j=b), d_u, `eq:variable_surprisal`, `eq:overall_ambiguity`, unlabeled hypothetical Q-tilde, following definition of U-tilde, `eq:ambiguity_gain`, `eq:fguide`, and neighbor union C(Delta D_u). Parent free-variable LLRs remain unchanged during hypothetical scoring; no BP call per search node. |
| 5: admission | `admission.hpp`: Step 5 equations B_c, P_c, K_run; `Dual-score admission` defines K_s/K_g, S_c/G_c, Unique union E_c and cardinality test. Select globally across parents. Deduplicate and refill guide-first, then solve only after guide exhaustion. `Execution of hard-decimated BP` requires parent-state inheritance where possible, fixed-edge removal and original-H checks before and after iterations. |
| 6: retention | `reliability.hpp` and `decoder.hpp`: recompute `eq:average_llr`, `eq:variable_confidence`, then `eq:bp_reliability` and `eq:beam_retention`. Larger R is better; retain at most K_keep <= K_run from unsuccessful new instances. Repeat at most C_max cycles. Do not carry old parents merely because the old controller did. |
| 7: fallback | `decoder.hpp`: `Step 7: OSD Fallback`, B-star argmax R and original-H validation equation. Use that state's full signed LLR vector, or physical channel priors if no retained state exists. Proposed first implementation calls existing OSD-0 bridge. |

## Fork API contract to implement later

Current fork audit: `reference_bp.hpp::ReferenceBp::decode` has structural masks
and terminal history, but cold-start flooding sum-product only. `stateful_min_sum.hpp`
has `reset`, `replace_fields/replace_hint`, `advance`, `snapshot/restore`, `llrs` and
`decision`; its snapshot owns q/z, LLRs, decisions and model/shot/numeric identities.
It has neither structural masks nor an iteration-history ring. The old project
`HardFixedMinSumSession` is archived and is **not** a ready v2 kernel.

The proposed opt-in fork session shares immutable H and physical priors, owns
mutable edge messages and a bounded history, and is non-reentrant. Inputs are
binary syndrome `(M,)`, sorted unique in-range `(index, bit)` assignments and
iteration/history budgets. Reset clears every prior-shot field. Snapshot copies
are owned, including active mask, residual syndrome and history; inheritance
requires matching model, numeric policy and shot and extension of parent fixation.
Reject malformed shapes, conflicting assignments and foreign snapshots at the
native boundary. Posterior history has shape `(completed_window, N)` with an
explicit active mask; fixed-column values must not enter free-variable reductions.
An advance call exposes a complete decision and iteration history without Python
iteration callbacks. Project native orchestration validates original H and predicts
A; no truth argument exists anywhere in this API. OSD receives `(M,)` syndrome
and `(N,)` signed reliability with original H. Its invocation flag resets to false
each shot and becomes true exactly when fallback is invoked.

## Proposed strict fields (validated now, execution unavailable)

| Fields | TeX parameter / contract |
|---|---|
| `bp.initial_iterations`, `bp.candidate_iterations` | Positive BP execution budgets; TeX does not supply defaults |
| `bp.history_window`, `bp.average_llr_clip` | W and L_c > 0; W cannot exceed either configured iteration budget |
| `search.selected_checks`, `search.local_variables`, `search.max_fixations` | Top-check count, m, q; positive integers with q <= m |
| `search.max_cycles` | Positive C_max; no old direct-OSD zero-cycle identity |
| `search.beta`, `search.guidance_strength` | Finite nonnegative beta and lambda |
| `admission.k_run`, `admission.k_keep` | Independent positive limits with K_keep <= K_run |
| `fallback.backend`, `fallback.osd_order` | Fixed `ldpc_osd_only`, 0 |
| `numerics.dtype`, `numerics.fast_math`, `native_threads` | float64, false, 1 |
| `output` | `minimal_results`, `search_bp_results/1`, root and Parquet compression/shot-flush controls |

Names/defaults and the budget/window constraints are proposed implementation
contract choices, not additional TeX equations. No old expansions-per-cycle,
beam_width, retention_score, soft hints, optional goal-test, telemetry or post-solution
optimization keys survive. Strict unknown-key/nonfinite/old-version rejection
prevents relabeling SEARCH-BP-1.0. Kernel-selection fields await a numerical decision.

## Ambiguities that must be resolved before decoding implementation

1. BP algorithm (sum-product versus min-sum), schedule, scaling, saturation and
   zero-LLR hard-decision ties are not specified. L_c clips history only; it does
   not authorize adopting the existing clipped soft-hint kernel.
2. `eq:average_llr` assumes W completed iterations. Short history, inherited history
   across a mask transition, and early termination need an explicit policy.
3. U-tilde's variable normalization could retain the parent's denominator or use
   the child's free count. The text says set newly fixed ambiguity to zero but
   does not explicitly replace the denominator. Empty free sets also leave U/R
   undefined. Empty neighborhoods and the empty minimum in the fractional bound
   require a contradiction policy; no rule has been silently supplied.
4. M denotes both matrix check count and the selected-check budget; BottomM uses
   m in prose. Config names disambiguate symbols but do not settle undersized
   neighborhoods or oversized selection budgets.
5. Unsatisfied descendants' “same correction-search rule” does not fully specify
   subsequent check selection, whether the local variable restriction persists,
   or whether canonical zero exclusions count toward q's additional fixations.
   These choices affect the stated local bound. Direct search-solution detection
   and ordering of simultaneous valid candidates also need specification.
6. Unique patterns from different parents can have different message histories
   and guide scores. Deduplication key and donor choice need an explicit rule.
   Beyond weight/index initial branching, Top/Bottom/admission/retention/argmax
   ties are unspecified. Proposed deterministic secondary order is canonical
   assignment, parent ordinal, then generation ordinal; it is not implemented.
7. “Full signed LLR” for fallback does not specify final versus averaged free LLRs
   or reliability magnitudes for removed fixed variables. Do not reuse v1's
   signed physical magnitudes without approval of that numerical policy. An empty
   candidate pool before C_max and retention exhaustion need an exit policy.

These are deferred algorithm decisions, not blockers to this architectural stage.
The model's existing zero-probability normalization, physical circuits, both
extraction sectors, verified Z projection, DEM correlations and all 12 BB logical
observables remain unchanged.

## Migration inventory and validation

Exact moves: [legacy/search_bp_v1/moves.txt](legacy/search_bp_v1/moves.txt).
Mixed config/adapter/worker/pipeline snapshots preserve the removed integrations
under `src/qec_bp_benchmark/legacy/search_bp_v1`; active generic portions stay in
place. Historical reader code is isolated under `analysis/legacy/search_bp_v1` and
`storage/legacy/search_bp_v1`; compatibility dispatch does not load native v1 code.
Historical tests are outside active pytest collection and CMake targets.

Generic graph/model, screened-reference search, hybrid HSBP code, upstream BP-OSD
and beam adapters, sampler, circuit/DEM/model preparation, scheduler, ResultStore
and ShotChunkBuffer remain active because they serve independent profiles or
generic infrastructure. The fork's source bytes and historical scientific runs
are unchanged. Actual validation results are recorded in STATUS.md.
