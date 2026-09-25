# Active tests

`python -m pytest -q` runs baseline, simulator, BB144, config, storage and
import tests. Historical decimation tests are preserved under `tests/legacy/`
and target the pre-migration commit documented in `docs/legacy/decimation/README.md`.
Final AF-BP validation adds exhaustive tiny graph lifts, randomized biclique
and exact-score oracles, a full tiny qDither paper-equation oracle, and a
four-round exact iteration failure. Run `bash scripts/check_af_bp_native.sh`
with each of `debug`, `asan`, and `ubsan` for standalone native checks. The
112-decision pristine Beam comparison is
`python python_scripts/validate_beam_counter.py assets/acceptance/NEW_BEAM_DIRECTORY`.
The previous coverage inventory below is historical.

---

# Verification

Run python -m pytest -q in search_decimation. Tests cover strict configuration and
identities, actual pinned native imports, all physical default circuits, independent
BB algebra and measurement projections, exact noise operations, canonical DEM
fixtures/controlled faults, immutable artifact round trips, complete scalar-vs-native
BP traces, boundaries/ownership/reuse, and 288 pristine-vs-fork ordinary BP-OSD outputs.

bp_oracle.py is test-only scalar code; no production module imports it.
bposd_regression_driver.py runs identical workloads with independent import paths.
native/ contains standalone C++ checks used in Debug and ASan/UBSan builds.
No long statistical experiment or performance claim is part of this suite.

Stage 4: search_oracle.py is an independent explicit-matrix exhaustive orchestrator;
test_search.py checks worked examples, exact lower bounds/top K/IDs and 560 complete
native-vs-oracle calls. test_decoders.py compares actual baseline APIs, fresh/reused
objects and reversed shot order, accepting valid OSD outputs with false BP flags.
Stage 5: test_pipeline.py uses actual native backends for serial/spawn/replay,
checks short batches, warmup isolation, failure/null labels, uint64 Parquet fields,
strict pairing, bounded out-of-order tasks, timing boundary, optional diagnostics,
worker/run exceptions, interrupted paired writes, partial-run replay and preserved
source bytes. test_provenance.py checks Git worktree files and dirty source state.

Stage 6: test_analysis.py checks known Wilson intervals, hand-counted disjoint block
components, BB dependence/denominators, zero and all-failed cases, exact linear quantiles,
empirical CDF/survival, unsupported pooling/duplicates, incomplete/corrupt saved runs,
standalone plots, visible zero-event limits and truth-free analysis imports. A new
provenance test restores the fork patch in a pristine worktree and checks every opt-in
source byte, including the ignored C++ binding. Clean acceptance repeats the suite,
upstream tests, native sanitizer/debug checks and all-four-code full smoke/replay.

Verbose CLI regressions cover quiet default output, serial/spawn progress, replay
totals independent of YAML shot count, and exact scientific equality with quiet runs.
The interrupted-run test checks that verbose failure output never reports unsaved
batches or successful completion.


Hybrid Stage 1 tests live in test_hybrid_config.py: strict configuration/budgets,
ablation/CS0 identities, explicit unavailable/unknown dispatch, all templates,
local edit/symlink preservation and numerical-import bootstrap. test_decoders.py
compares actual CS0 with direct upstream results across every 4-bit syndrome and
reused/fresh sessions. Hybrid numerical kernels are now covered by the Stage 2-3 suites below.

Hybrid Stages 2-3 add test_hybrid_bp.py and independent min_sum_oracle.py,
test_hybrid_search.py and independent hybrid_oracle.py, plus bounded physical
service integration in test_hybrid_circuit_integration.py. Manual
check_hybrid_restoration.py compiles a new opt-in binding from pin + tracked patch.
Source mutation/identity and every fork-file restoration are checked. Native
release/Debug/sanitizer tests cover actual OSD comparisons, search partitions,
reference equality and injected allocation failure recovery.

Hybrid Stages 4–5: test_hybrid_storage.py covers deterministic native terminal paths,
nulls, signed residuals, cycle/phase validation, multi-table interruption/corruption,
v1 projection and physical surface/BB worker/replay equality with all ablations.
test_hybrid_analysis.py uses hand-checkable speed/accuracy counterexamples, exact
paired identities, conditional denominators, bootstrap reproducibility, incompatible
contexts and replay independence. Historical v1 writer tests explicitly project v2
runner rows into the unchanged v1 schema to keep exercising that boundary.

Final restoration: `python tests/check_hybrid_restoration.py` restores the locked
ldpc patch into a temporary worktree, checks every source hash, rebuilds both opt-in
bindings plus a clean project extension, checks compiled/source identities and runs
all four native tests. It reuses the existing conda dependencies and cleans up its
own temporary worktree. `python python_scripts/accept_hybrid.py --output NEW_DIR`
is the bounded command-line E2E acceptance harness (including report/notebook).

Legacy layout: config/circuit tests load tracked config/legacy/*.yaml.example files.
Template discovery tests cover both directory levels and preserve legacy local
edits as well as active-file edits and symlinks. This avoids dependency on ignored
local configs in fresh checkouts.

Consumer migration: test_analysis_migration.py checks preserved Python hashes,
shot/unequal-batch bootstrap equality against the legacy implementation (including
int64 overflow and nulls), analysis-only settings, absence of decoder/runner imports,
CLI stdout/progress and executed notebook behavior. The v1 projection test also
compares current and preserved readers. The full suite and requested-data notebook
are indexed under docs/test_results/analysis_migration_*.

`test_quick_plots.py` checks trusted on-demand column projection, all-shot timing
row retention, and failure-count/Wilson-interval parity with the verified reader.

SEARCH-BP-2.1 migration coverage is in `test_search_bp_v2_contract.py`: explicit
version/config rejection, execution guards, absence of old native symbols,
independent failure-label cases, exact six-field output and grouped spawn output.
`test_simple_results.py` retains generic naming/writer/serial integration checks.
`test_hybrid_storage.py` checks paired scientific result equality across worker
and warmup settings; raw samples and event tables are no longer emitted.
SEARCH-BP-1.0 tests are preserved under `legacy/search_bp_v1/` and excluded from
pytest collection and CMake. Baseline/circuit/native numerical tests remain active.

Stage 2 fork tests: `test_decimated_bp.py` checks actual pinned BP outputs/LLRs,
an independent scalar masked-message/history oracle, ring wrap, zero/short history,
continuation/restore, descendant message inheritance, contradictions, input
boundaries, saturation, exact iteration counts and reset/ownership. The native
`test_decimated_bp` target adds 360 pinned C++ BP comparisons and participates in
Debug/ASan/UBSan and clean opt-in restoration. Existing baseline tests are retained.
LPM-DP Stage 2 additionally compares the exposed completed-round check messages
with the scalar oracle, reconstructs posteriors from them, preserves them across
restore/copy/move, and proves fixed child edges keep both message directions zero.
LPM-DP Stage 3 adds `native/test_lpm_dp_decoder.cpp` for the distinct native-only
decoder state machine, including per-parent ordering, hard masks, warm starts,
online reference retention, bounded snapshots, recursive cycles, terminal OSD,
shot reuse and non-reentrancy. No simulator path is exercised.
LPM-DP Stage 4 adds `test_lpm_dp_stage4.py` for strict configuration/native mapping,
truth-free adapter calls, exact failure/OSD semantics, five-column output and a
bounded Surface-d3 run with unchanged Beam/BP-OSD adapters. Final validation runs
that smoke under one-worker serial and two-worker spawn execution and compares all
saved scientific fields except latency. `test_provenance.py` also proves that the
clean dependency bootstrap restores every untracked source hashed by the hybrid
binding, including the decimated-BP header.

SEARCH-BP-2.0 Stage 3: `test_search_bp_stage3.py` independently recomputes the
TeX formulas and both bounded-tree policies, with exhaustive probe patterns,
randomized scalar tree comparisons, direct solutions, snapshot immutability and
repeated-shot reset. `native/test_search_bp_stage3.cpp` adds the sixth native
Debug/sanitizer/restoration target. These tests do not execute recursive admission
or fallback and do not run production simulations.

SEARCH-BP-2.0 Stage 4: `test_search_bp_stage4.py` compares the full native decoder
with an independent Python orchestration reference, using scalar Stage-3 formulas
and the unchanged fork BP/OSD services. The seventh native target
`test_search_bp_stage4` checks global quotas/refill/dedup, exact donor inheritance,
R retention, three recursive cycles, fallback inputs/call count and reentrancy.
Native test callbacks are compile-time-only; the production result has no telemetry.

Stage 5 adds `test_search_bp_stage5.py`: strict config/native mapping, truth-free
adapter and independent H/A checks, worker pairing and controlled timing/failure
labels, plus paired Surface/BB single/spawn-worker smoke runs with SEARCH-BP,
beam8 and BP-OSD-CS0. New files have exactly the five `_results.parquet` fields.
Source audit verifies unchanged physics, sampler/seed/pairing and native code.
# SEARCH-BP-2.1 validation

`test_decimated_bp.py` and `test_search_bp_stage3.py` compare scalar messages,
trailing means and all score terms with explicit tight tolerances and exact GF(2).
`test_search_bp_stage4.py` and its standalone native test cover independent global
admission, retention and fallback. Stage-5 tests include correction-level repeat/
reset checks on Surface d3 and BB72 d6, with all 12 BB observables, plus paired
serial/spawn minimal-output smoke runs. `native/benchmark_search_bp.cpp` is a
standalone synthetic decoder-only benchmark; see the active implementation audit
for commands and limits. Historical evidence below remains stage-specific.
