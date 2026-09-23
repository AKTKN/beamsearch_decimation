# Specification-to-implementation-to-test traceability

SEARCH-BP-2.0 simulator integration is complete through Stage 5. The final
[active implementation audit](search_bp_implementation.md#tex-to-code-traceability)
maps every TeX step/equation to functions and independent tests. Final-pass evidence
is under `test_results/search_bp_final_*`; historical evidence below is preserved.
[search_bp_stage5.md](search_bp_stage5.md) maps configuration, adapter, minimal
output and invariant checks to source/tests. Native decoding is complete through Stage 4. [search_bp_stage4.md](search_bp_stage4.md) maps global admission,
retention, recursive execution and OSD fallback to source and tests. Stage-3 Steps 1–4 are implemented;
[search_bp_stage3.md](search_bp_stage3.md) maps each equation to source and tests. The exact TeX references and future native/fork
boundaries are in [search_bp_v2_design.md](search_bp_v2_design.md).

Stage 2 BP API traceability: [decimated_bp.md](decimated_bp.md).
`refined.tex`'s physical LLR and residual definitions map to fork
`decimated_bp.hpp::Session`; its `eq:average_llr` maps to the bounded ring/mean API
when history_count == W. `test_decimated_bp.py` supplies a scalar reference and
edge-mask/history/state tests; `native/test_decimated_bp.cpp` compares pinned
parallel min-sum. The source inventory and restoration test cover the new header.
No confidence/check-ranking/search/admission equations are implemented in the fork.

## LPM-DP 1.0 Stage 1

The standalone-only implementation and executed evidence are detailed in
[lpm_dp_stage1.md](lpm_dp_stage1.md).

| Note requirement | Implementation | Behavioral evidence |
|---|---|---|
| Exact eight settings and parent summary | `lpm_dp_model.hpp::Settings`, `summarize_parent` | defaults/ranges, clipped history, fixed/disconnected exclusion, ties |
| Sparse one/two-check region and nested locations | `select_region` | single/pair/shared-variable and nesting fixtures |
| Cavity field and joint parity labels | `build_local_fields` | selected-message exclusion, ordered clipping, shared label |
| Boundary/full-mass/list DP | `build_dp_tables`, `evaluate_fixation_count` | one/four-state, boundary/empty/infeasible fixtures; random exhaustive oracle |
| Exact top-K mass and largest q | `choose_fixation_count` | worked 0.9 example, fallback, random selected-q comparison, q=64 |
| Standalone composition and input contract | `generate_candidates`, `ParentView` | end-to-end and malformed-input cases; Debug and ASan/UBSan |

The headers are included in the project source-identity inventory. CMake adds only
the standalone native target; no fork, binding, decoder, config or runner path is
changed.

## LPM-DP 1.0 Stage 2

The exact-message fork audit and ownership/memory report are in
[lpm_dp_stage2.md](lpm_dp_stage2.md).

| Requirement | Implementation | Behavioral evidence |
|---|---|---|
| Exact completed-iteration `mu_(a->j)^(T)` | `decimated_bp.hpp::Snapshot::check_to_variable`; iteration writes the snapshot-owned buffer it consumes | scalar edge-message oracle plus posterior reconstruction each round |
| Exact restore and owned parents | snapshot-owned `z_`; default copy/move; restore does not recompute/zero free entries | Python restore/detachment checks; native copy/move/restore checks |
| Fixed child edges stay disabled | `reconstruct` zeros both `q_` and `z_` on fixed columns | before/after child-iteration edge-mask checks |
| Bounded memory | one additional `8E` per retained/materialized snapshot; former session `8E` workspace removed | payload assertions and BB72 exact memory calculation |
| Preserve existing decoders | no update/stopping/decision/controller changes | pinned BP and deterministic Beam/BP-OSD/SEARCH-BP regressions |

| Migration requirement | Implementation | Evidence |
|---|---|---|
| Old algorithm excluded from active build | module.cpp, CMakeLists.txt, native_sources.py; native/legacy/search_bp_v1 | test_search_bp_v2_contract.py checks missing old symbols |
| Explicit v2 identity, reject v1 | config.SearchBP, config schema /3 | old config and removed-option rejection tests |
| No premature v2 execution | require_available_decoder | adapter and runner fail before filesystem effects |
| Five-field output and failure-inclusive latency | storage/minimal.py, runner | independent label cases, serial/spawn baseline output tests |
| No run/context pooling, exact OSD denominator | analysis/simple_search_bp.py | saved-data summary integration |

Historical SEARCH-BP-1.0 traceability is preserved under legacy/search_bp_v1.
The table below also includes historical acceptance evidence, not new-run output.

| Contract/specification | Implementation | Behavioral evidence |
|---|---|---|
| Full physical circuit, verified Z projection, BB12 | circuits/, artifacts.py | test_circuits.py, test_dem.py |
| Undecomposed mechanisms/separators/zero removal | dem/model.py | test_dem.py |
| Flooding buffers, clip, L<0, structural fixation | ldpc/src_cpp/reference_bp.hpp | test_bp.py, bp_oracle.py, native/test_reference_bp.cpp |
| Terminal history pool, exact fixed-q patterns | native/search.hpp::pool/screen | test_search.py exact ordering/counts and worked example |
| All-free weighted lower bound and contradiction filter | native/search.hpp::score_unchecked | exact completion enumeration in test_search.py |
| All retained cold-start completions, physical-cost/lex winner | native/search.hpp::decode | 560 full-oracle comparisons; multiple-success/rescue/failure checks |
| Actual upstream adapters and native conventions | decoders/__init__.py | test_decoders.py, test_upstream_regression.py |
| Immutable/lazy plan, same-shot delivery, truth separation | runner/plan.py, worker.py | test_pipeline.py pairing/warmup/serial/spawn checks |
| Optional parent progress without changing scientific outputs | run/replay --verbose; pipeline.run_benchmark(verbose=True) | quiet/serial/spawn/replay CLI equality and interrupted-run progress tests |
| Complete service timing, mode/thread labels | decoders + runner/worker.py | timing-boundary instrumentation; actual worker threadpool checks |
| Null failure fields, BB block components | storage/schema.py, failure_labels | test_pipeline.py 12-observable/null/seed/Parquet tests |
| Bounded spawn, exceptions, parent-only atomic paired writes | runner/pipeline.py, storage/ | bounded/reordered/worker-error/second-shard interruption tests |
| Source bytes, dirty patches, worktrees | provenance/ | test_provenance.py, source ZIP checksum tests |
| Saved samples and incomplete committed subsets | runner/pipeline.py::_replay_tasks | actual native replay and partial-source tests |

Historical Stage 4–5 commands/results and preserved runs are in
docs/test_results/stage_4_5_summary.json. Later-stage checks follow below.

## Stages 6–7 extensions

| Contract/specification | Implementation | Behavioral evidence |
|---|---|---|
| Verified manifests, committed subsets and explicit selection | analysis/io.py | incomplete/corrupt/duplicate/identity tests |
| Summed block components and conditional denominator | analysis/statistics.py | hand-counted unequal batches and BB multi-bit fixture |
| Two-sided Wilson / zero-event bounds | statistics.wilson_interval, plots.plot_failure_rates | known interval endpoints; triangle data equal actual upper endpoint |
| CPU/wall quantiles, ECDF/survival and N(1-q) flags | statistics.py, plots.py | exact interpolation/ties, missing diagnostics and failure times |
| No implicit model/noise/decoder/mode/run pooling | protected GROUP_KEYS + execution/comparison identities | incompatible-group tests and replay duplicate rejection |
| Notebook as consumer, standalone figures | notebook/benchmark_analysis.ipynb, analysis/report.py | actual notebook execution and PNG/PDF/JSON export |
| Ignored authored source in fork patches/archives | audit_dependencies.py, build_dependencies.py, provenance/ | pristine-worktree restoration of bindings.cpp and ZIP byte checks |
| Fresh pinned-source build | independent acceptance workspace/prefix + build helper | source-build logs, native import/source/binary identities |
| Full all-four-code smoke/worker/mode/replay equality | run/replay CLIs + analysis/validation.py | complete 32-shot-per-instance acceptance runs |

The current complete results and limits are in acceptance_report.md. Historical
Stage 1–5 reports above remain preserved; they are not substituted for the final
clean-environment evidence.

## Git distribution maintenance

.gitignore excludes mutable scientific outputs, working YAML/notebooks, build
products and nested dependency checkouts. scripts/setup_local_files.sh restores
versioned templates without overwriting local work. See distribution.md for
publication checks; scientific algorithms and historical artifacts are unchanged.


## Hybrid migration Stage 1

| Contract | Implementation | Evidence |
|---|---|---|
| HSBP-ALG section 10 strict nested settings and resolved budgets | config.Hybrid, HybridSearch/BP/Fallback/Numerics | test_hybrid_config valid/invalid/identity/JSON cases |
| HSBP-ALG section 6.3 distinct actual CS0 and historical CS10 | Bposd0, explicit adapter/identity routing | test_decoders direct pinned outputs and reset; test_hybrid_config identities |
| No placeholder hybrid or beam fallthrough | require_available_decoder, runner preflight, explicit adapter branches | unknown and hybrid rejection before model/output access |
| HSBP-ALG section 9 ownership/source boundaries | docs/hybrid_migration.md | documented Stage 2-3 obligations; not a claimed kernel test |
| Preserve user rates/local templates and bootstrap | setup_local_files.sh, import-light config/preflight | temporary setup edit/symlink checks and fresh-interpreter import check |
| Reconstructible configuration sources | provenance captures .example files | source archive checks in test_pipeline |

Actual Stage 1 validation logs and limitations are recorded in STATUS.md; historical
acceptance results above are not new hybrid evidence.

## Hybrid Stages 2-3

| Contract | Implementation | Executed evidence |
|---|---|---|
| Stateful flooding min-sum and finite replacement fields | fork stateful_min_sum.hpp, hybrid_graph.hpp | test_hybrid_bp.py with independent min_sum_oracle.py; clipping, signs, repeated minima, degenerate graphs, reset and finite-hint disagreement |
| Direct signed-LLR CS/order-zero without BP | fork osd0_bridge.hpp | native/test_hybrid_bp.cpp: 1,024 actual-kernel CS0/OSD0 comparisons including ties and inconsistent/rank-deficient matrices |
| Branch partition, local rejection, fractional bound | native/hybrid_search.hpp | exhaustive tiny matrices/patterns/completions in test_hybrid_search.py; native branch partition checks |
| Persistent search/BP, ablations, first-generated goal | native/hybrid.hpp | 350 independent full-oracle cases; 768 native reference/optimized comparisons; deterministic terminal/cap/depth fixtures |
| Native CPU/wall counters/events and failures | hybrid_telemetry.hpp, hybrid_bindings.hpp | sums/nulls/rounds, numerical failure fixture, injected native allocation failure and recovery |
| Ownership/concurrent independent instances/physical H/A | DecoderAdapter and native model | thread-pool reuse tests, 4 surface + 4 BB shots across all three profiles with 12 BB labels |
| Authored/transitive source hashes and clean binding restore | source_files.py, native_sources.py, CMake, audit/build helpers | per-file mutation/runtime rejection, pristine patch bytes, separate source-only worktree compilation |
| Native memory/UB safety | CMake tests | release, Debug and ASan/UBSan; see STATUS.md for final commands and logs |

Hybrid saved tables and paired hypothesis analysis remain Stages 4-5.

## Hybrid experiment migration (Stages 4–5)

| HSBP-EXP-1.0 requirement | Implementation | Behavioral evidence |
|---|---|---|
| §§3–4 paired execution/timing | runner/worker.py + native post-service export | test_hybrid_storage paired workers/replay/warmup; legacy timing boundary tests |
| §§5–6 labels/versioned tables/atomic output | storage/schema.py, telemetry.py, storage writer; analysis/io.py | deterministic all-stage roundtrips; none/phases; fourth-shard interruption; missing/corrupted/duplicate data; v1 projection |
| §7 exact cost identity | analysis/hybrid.py | hand-counted fewer-OSD-but-slower case; per-shot and aggregate identity; residual errors |
| §8 paired accuracy and uncertainty | analysis/hybrid.py + statistics.py | faster-but-less-accurate fixture, conditional denominators, discordance, shot/batch bootstrap reproducibility, replay separation |
| §§9–10 saved-data reporting/provenance | report.py, plots.py, notebook template, pipeline/provenance | bounded CLI report and executed notebook; v2 model sizes and clock metadata |

Exact new schemas and limitations are in hybrid_data.md. Stage 6 clean restoration
and final migration acceptance remain separate from these software checks.

## Hybrid Stage 6 completion

`tests/check_hybrid_restoration.py` verifies the locked patch and every ldpc source,
compiles both bindings and the project from a binary-free isolated tree, and executes
native tests/source-digest checks. `python_scripts/accept_hybrid.py` provides a single
bounded final workflow with fresh circuit artifacts, worker/mode/replay equality,
all 12 BB outcomes, report and notebook. Final review adds phase-result vocabulary,
terminal-stage correspondence and prefix interval validation; corruption fixtures
exercise each check. See hybrid_acceptance.md and STATUS.md for actual results.

## Saved-data consumer migration

| Requirement | Implementation | Evidence |
|---|---|---|
| Preserve previous analysis | analysis/legacy + snapshot.json; legacy scripts/template | Byte hashes, legacy v1 projection and report tests |
| Independent analysis settings | analysis/config.py; config/analysis.yaml.example | Strict/path tests and no simulation-config fallback |
| Same paired inference with bounded working memory | analysis/bootstrap.py and hybrid.py | Complete legacy parity on shot/unequal-batch draws, large integers and nulls |
| Active-environment notebook and maintained default | execute_notebook.py; notebook template runtime guard | Executed consumer test and requested 60,000-shot saved run |
| Current consumer provenance and progress | analysis/runtime.py; report.py; analyze CLI | Source hashes, report checksum verification, stdout/stderr test |

## Lightweight saved-data notebook

The 2026-09-21 notebook simplification maps the requested saved-data-only workflow
to direct reader/statistics/plot calls in both current notebooks. Loading and
drawing are separate cells; detailed hybrid/paired/bootstrap analysis stays in
the full-report API/CLI. See STATUS.md for validation and the source audit.
Legacy templates and scientific artifacts are unchanged.

The subsequent explicit request for no validation applies only to the local
interactive notebook. `analysis/quick_plots.py` supplies plot-specific projected
reads, Arrow failure aggregation and existing plot exports. Tests in
`tests/test_quick_plots.py` compare physical-shot counts/intervals to the verified
reader and check that unrelated columns are never requested. Execution evidence
and source hashes: docs/test_results/notebook_on_demand_verification.json.
