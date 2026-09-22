# SEARCH-BP-2.1 active implementation and final audit

The active `search_bp` service is `_native.SearchBP2Decoder`, reached through the
existing Python `DecoderAdapter`. Root [refined.tex](../refined.tex) is normative
and unchanged. The [Stage-1 design](search_bp_v2_design.md) and Stage-3/4 decisions
record the user-approved local-variable and fallback conventions. The simulator
integration is described in [Stage 5](search_bp_stage5.md).

The fork owns parallel minimum-sum BP, structural hard fixations, snapshots and
bounded LLR history. Project C++ owns scores, local searches, global admission,
retention and recursive control. Existing fork OSD-CS order zero supplies fallback.
Python constructs a decoder once per worker/model, passes only the syndrome, and
independently validates original H/s and computes all original A observables.
Truth comparison occurs afterward in the worker. No physics or sampling changes
are part of this pass.

## TeX-to-code traceability

Paths abbreviated `native/` are under `src/qec_bp_benchmark/`; `fork/` means
`external_lib/ldpc/src_cpp/`.

| TeX step / equation | Active function and file | Independent checks |
|---|---|---|
| 1: physical priors, initial BP, H e = s | `Decoder::run`, `native/search_bp_decoder.hpp`; `Session::reset_from_channel`, `continue_iterations`, `iteration`, `fork/decimated_bp.hpp` | pinned upstream comparisons, scalar excluded-edge messages, actual round counts, zero syndrome |
| 2: `average_llr`, `variable_confidence` | `Session::record_history`, `clipped_mean_llr`; `ParentScores` in `native/search_bp_scores.hpp` | explicit trailing clipped vectors, scalar tanh, short/complete windows and continuation |
| 3: `check_probability`, `check_ambiguity`, Top-M | `ParentScores`; `select_checks`, `native/search_bp_search.hpp` | scalar full recomputation, empty checks, satisfied/unsatisfied checks and deterministic ties |
| 4: `local_variables`, `node_residual`, `fractional_heuristic`, `fsolve`, `variable_surprisal`, `overall_ambiguity`, `ambiguity_gain`, `fguide` | `select_variables`, `LocalSearch::{solve_tree,enumerate,emit}`; `Scorer::{load,evaluate}` in `native/search_bp_scores.hpp` | independent combinations/tree reference, exact XOR, all-free fractional coverage, all formula terms, both local policies |
| 5: global dual-score quotas, Unique, refill, inherited BP | `admit`, `extend_pattern`, `native/search_bp_admission.hpp`; `Decoder::run`; `Session::inherit_descendant` | independent full-sort admission, odd/even quotas, duplicate donors, global execution limit, inherited free messages |
| 6: `bp_reliability`, `beam_retention`, recursion | `reliability`, `retain`, `Decoder::run`, `native/search_bp_decoder.hpp` | scalar R and full-sort K_keep, three cycles/multiple parents, fresh searches and shot reset |
| 7: optional argmax-R OSD-0 fallback and original H/s | `fallback_llrs`, `Decoder::run`, `Decoder::result`; unchanged `fork/osd0_bridge.hpp` | disabled-fallback failure, exact chosen state/input, signed DBL_MAX, successful/failed OSD flag |

The independent references live in `tests/test_decimated_bp.py`,
`tests/test_search_bp_stage3.py`, `tests/test_search_bp_stage4.py` and the matching
native tests. GF(2) arrays and selected patterns compare exactly. Formula and ring
comparisons explicitly use relative tolerance 1e-12 and absolute tolerances from
2e-14 to 1e-12. The Python controller deliberately reuses the separately tested
fork BP/OSD; it is an independent orchestration reference, not a second OSD.
The native observer asserts admission, inheritance, R ordering and fallback state
inside the production loop, but is compiled only into standalone tests.

SEARCH-BP-1.0 source/bindings/contracts remain under named `legacy/search_bp_v1`
directories. Active includes, CMake inputs, source identities and simulator
dispatch select v2 only. Old settings/bindings are rejected/absent; no old frontier,
soft hint, score, adaptive quota or telemetry path is called by `search_bp`.
Other historical decoder identities retain their own implementations.

## Exact decoder configuration

Required version is `algorithm_version: SEARCH-BP-2.1` within
`config_schema_version: search_bp_config/4`. Kind/profile/name are `search_bp`;
enabled defaults to true. These are the complete native algorithm settings:

| YAML field | Default |
|---|---:|
| `bp.initial_iterations` | 30 |
| `bp.candidate_iterations` | 20 |
| `bp.history_window` | 8 |
| `bp.average_llr_clip` | 25.0 |
| `bp.scaling_factor` | 1.0 |
| `search.selected_checks` | 2 |
| `search.local_variables` | 4 |
| `search.local_variable_policy` | `refresh_descendant` |
| `search.max_fixations` | 2 |
| `search.max_cycles` | 2 |
| `search.beta` | 1.0 |
| `search.guidance_strength` | 1.0 |
| `admission.k_run` | 4 |
| `admission.k_keep` | 2 |
| `osd_fallback` | true |
| `native_threads` | 1 (fixed) |

Counts are positive strict int32, K_keep <= K_run, q <= m in both simulator
policies, W <= both BP budgets. Clip is finite in (0, DBL_MAX/(2W)], scaling in
(0,1], beta/lambda finite nonnegative. OSD-0, binary64, no fast-math and no FP
contraction are fixed contracts. Unknown/legacy fields are rejected. The example
overrides initial/candidate iterations to 4 and W to 2 for bounded smoke testing;
its physical rate is a validation input, not a production recommendation.

`fixed_root` keeps the initial bottom-m set and chooses the lowest-index residual
unsatisfied descendant check. The default `refresh_descendant` chooses the most
ambiguous residual-unsatisfied check using hypothetical Q, then bottom-m currently
free variables using the parent's confidence. Both use canonical physical-weight,
then index branching; q counts every newly fixed zero and one. Patterns deduplicate
within a tree and by full resulting pattern at global admission. Search state is
discarded each cycle. Exact tie and donor rules remain those in
[Stage 4](search_bp_stage4.md#cycle-algorithm-and-deterministic-policies).

## Numerical conventions

Physical LLR is log((1-p)/p), evaluated as `log1p(-p)-log(p)`, for 0 < p <= 1/2.
Positive LLR favors zero; the pinned BP hard-decision/edge-sign tie at zero uses
bit one. Fixed variables have no active edges and fixed-one columns XOR into the
residual. Fixed posteriors are signed infinity, excluded from scores and BP sums.
Degree-one checks use scaled DBL_MAX; overflow protection saturates arithmetic at
signed DBL_MAX. History clipping does not clip the physical costs or BP messages.

History is an N-by-W ring of clipped posteriors plus N running sums. Each round
subtracts the outgoing slot and adds the incoming slot; no full iteration history
is retained. Descendants inherit free messages/posteriors and ancestor fixations
but reset the ring. Only unsuccessful, noncontradictory states with a complete W
enter search/retention. The generic fork API also supports short means over actual
samples and zero-sample clipped current LLRs. Fixed mean placeholders are ignored.

Hypothetical variable ambiguity retains the **parent free-count denominator**;
newly fixed ambiguity becomes zero. Only affected check Q values change. Empty
normalized sums contribute zero; an unsatisfied check without a free variable is
contradictory. Stable softplus computes surprisal. Scores use exact binary64 tie
comparisons; no epsilon, approximation or score mixing enters R.

OSD receives the highest-R retained state's **final signed LLRs**, replacing only
fixed infinities by signed DBL_MAX as explicitly requested. This orders their
reliability but does not constrain OSD to retain those bits. With no surviving
state, OSD receives the physical channel. With `osd_fallback=true`, exactly one
OSD call occurs on fallback; with false, exhaustion returns invalid without OSD.
Every returned correction is checked against original H/s.

## Allocation and memory audit

The final optimization changes only `native/search_bp_search.hpp` and
`native/search_bp_decoder.hpp`: reserve a branch prefix before copying its base;
grow reusable descendant scratch to visited check degree instead of allocating N
entries for every tree; and reserve the global pool from the first local candidate
batch, preserving geometric growth thereafter, with an overflow check. Candidate order, arithmetic, pruning,
budgets and enabled-fallback behavior are unchanged. No fork/OSD source changed.

Already present: immutable CSR/CSC adjacency built once, preallocated BP buffers,
affected-check Q updates, partial_sort for top-M/bottom-m/K_keep, index heaps for
dual-score admission, moving retained snapshots, and one Python call for the
whole native decode. Full fractional coverage still scans the graph as specified.
Python conversions and independent H/A validation occur only at service boundaries.
Snapshot restore still copies the donor's history before descendant history reset;
that simple existing fork path is retained. No cache or new allocator was added.

Let H_c be matrix checks, E edges, N variables, W window, and D current fixation
count. A snapshot owns q[E], final LLR[N], ring[NW], sums[N], fixed int8[N], syndrome
uint8[H_c], plus constant identity/numerical/cursor metadata. Its vector payload is
**S = 8(E + NW + 2N) + N + H_c bytes**. Continuation restores owned snapshots;
ordinary capture copies once, retention moves ownership.

Dominant live storage is:

* Immutable adjacency/priors/observables: O(E+N+H_c+nnz(A)), shared across BP states.
  Existing OSD also owns its sparse matrix and elimination workspace; elimination
  can have fill-in up to dense matrix scale and is not bounded by search quotas.
* One reusable BP session: S + 8E + N + H_c bytes of vector payload.
* At most K_keep parents plus K_run evaluated children: each S + 8N + 8D bytes
  of vector payload on this platform, plus vector/object/allocation overhead.
* Current candidate/search scratch: O(P_cycle D + N + H_c), plus one local
  pattern frontier/dedup set. P_cycle <= K_keep M_selected B, with B=P(m,q) for
  fixed_root and conservative B=max(P(m,q), sum_{d=1..q}m^d) for refresh_descendant.
  The latter is not generally bounded by the root-only P(m,q). D <= min(N,Cq).

Unadmitted patterns, rankings and local search scratch die before child BP starts.
`retain` erases discarded snapshots immediately; old parents are cleared before
the generation swap. All shot states die on return/exception. The reusable session
is fully reset on the next shot. Vector capacities and the system allocator can
keep released storage resident; RSS is not a count of live BP states. No historical
search telemetry, cross-cycle frontier or unbounded posterior history is retained.

## Output contract

There is one `<condition>_results.parquet` per condition, plus resolved config;
see [minimal output](simulation_output.md). Schema metadata is
`qec_schema=search_bp_results/2`. Exact columns in order are `shot_id: string not
null`, `decoder_name: string not null`, `logical_error: bool not null`,
`latency_ns: int64 not null`, `osd_called: bool nullable`, and
`correction_by_search: bool nullable`. SEARCH-BP requires both flags to be exact
nonnull booleans. `correction_by_search` is true only for a direct valid local-search
solution, never for initial/descendant BP or OSD. Logical error includes declared failure/invalid correction
or any logical mismatch; latency includes the complete adapter service and failed
shots, excluding simulation, truth comparison and I/O. No telemetry is saved.

## Final validation evidence

Evidence is under `docs/test_results/search_bp_final_*`. Commands use the
`search_decimation` conda environment:

| Check | Command / outcome |
|---|---|
| Dependency/fork identity | `scripts/build_dependencies.sh --check`: passed |
| Editable native extension | `python -m pip install --no-build-isolation --no-deps -e .`: built successfully |
| Focused BP/scalar/controller/adapter tests | `python -m pytest -q tests/test_decimated_bp.py tests/test_search_bp_stage3.py tests/test_search_bp_stage4.py tests/test_search_bp_stage5.py`: 115 passed; these tests are included in the final full suite |
| Full Python suite | `python -m pytest -q`: 330 passed, 1 skipped (unavailable historical local acceptance artifact) |
| Pinned upstream fork BP | `python -m pytest -q external_lib/ldpc/python_test/test_bp_decoder.py external_lib/ldpc/python_test/test_bp_decoder_input.py external_lib/ldpc/python_test/test_bp_serial.py`: 12 passed, six existing legacy/OpenMP warnings |
| Native Debug | CMake `QEC_BUILD_TESTS=ON`, Debug; all seven targets, CTest 7/7 |
| Native ASan/UBSan | same targets with `QEC_SANITIZE=ON`; CTest 7/7, leak detection and halt-on-error enabled |
| Clean patch restoration | `python tests/check_hybrid_restoration.py`: both fork bindings, fresh project extension/source identities and seven native tests passed |
| Config | `python python_scripts/validate_config.py config/search_bp.yaml.example`: passed |
| Serial / spawn smoke | `scripts/run_benchmark.sh assets/validation/search_bp_final/workers_{1,2}_final.yaml`: each has four shots per Surface d3/BB72 d6 condition, SEARCH-BP/beam8/CS0, 24 rows per run; exact scientific row equality excluding latency, five-field schema only |

The native build targets are `test_reference_bp test_search test_hybrid_bp
test_hybrid test_decimated_bp test_search_bp_stage3 test_search_bp_stage4`. Final
build directories are `assets/build/search-bp-final-{debug,sanitize}`. Sanitizer
CTest used `ASAN_OPTIONS=detect_leaks=1:halt_on_error=1` and
`UBSAN_OPTIONS=halt_on_error=1`. Restoration rebuilds the fork from its pinned
source/patch; the installed fork needed no source rebuild or patch regeneration
because its bytes were unchanged. The source audit includes exact production
diffs and confirms unchanged TeX, fork manifest/patch and protected science sources.

### Decoder-only profiling and bounded timings

`tests/native/benchmark_search_bp.cpp` constructs a synthetic Tanner graph with
64 checks, 128 variables and row degree eight. Contradictory duplicate checks
deliberately exercise two full cycles and fallback. This is not a physical noise
distribution, and all these stress inputs fail original H/s. Separate behavioral
tests cover successful corrections, intermediate choices and early returns.
Graph construction, syndrome generation and 16 warmup decodes are outside timing.

Before headers were saved under `assets/benchmarks/search_bp_final/before_headers`.
Both binaries were compiled with the same GCC 11.4.0 compiler and flags:

```bash
c++ -std=c++17 -O3 -g -fno-fast-math -ffp-contract=off \
  -Isrc/qec_bp_benchmark/native -Iexternal_lib/ldpc/src_cpp \
  tests/native/benchmark_search_bp.cpp -o assets/benchmarks/search_bp_final/after
assets/benchmarks/search_bp_final/after 100
```

The before build uses the saved-header include path. Seven process pairs alternate
before/after order, with 1,600 timed decodes per policy in each process. No builds,
tests or simulation run concurrently with these timing pairs. The table gives the
median of **process means**, with their observed range; these are not per-shot
median/tail estimates. Exact source diffs/hashes are in the source audit and all
samples in `search_bp_final_latency.json`.

| Policy | Before, microseconds/decode | After, microseconds/decode |
|---|---:|---:|
| fixed_root | 951.228 (930.921–960.897) | 949.949 (944.561–968.389) |
| refresh_descendant | 950.167 (944.772–1022.750) | 963.153 (955.749–988.901) |

There is **no demonstrated latency improvement**: fixed_root is essentially flat
and the refresh median is slightly higher, within overlapping observed ranges.
The changes are retained for simpler allocation behavior and smaller scratch,
not a speed claim. Earlier reservation experiments remain labeled `_initial`.

A separate `-pg` baseline build, run with the same 100 repetitions and inspected
with gprof, attributed about 52.9% of sampled self time to BP iterations and 31.0%
to upstream OSD sorting/row addition. These existing kernels were left unchanged.
Sampling/inlining and profiler overhead limit those percentages. A separate
cProfile of 2,000 zero-syndrome **adapter-only** calls identified binary validation
and sparse H/A multiplication as the visible Python boundary costs. No Python
objects are created inside native search/BP loops, and independent validation was
preserved. Neither profile measures or alters quantum simulation.

`/usr/bin/time -v` reported peak process RSS of 4,532 KiB before and 4,136 KiB after
for one 100-repetition benchmark process each. These include executable/runtime,
OSD and allocator storage; they are not live-state byte measurements or evidence
of a general memory reduction. Large physical-model peak memory was not measured.

Known limits: small synthetic and bounded Surface/BB cases do not establish
production accuracy, throughput, tail latency, or an advantage over beam8/CS0.
Large m/q remain combinatorial; exact ring storage scales with NW and beam states;
OSD elimination may dominate memory/time. Shared decoder objects are deliberately
non-reentrant. No production sweep, fresh conda-environment rebuild, multithreading,
approximate scoring or new pruning is part of this pass.
