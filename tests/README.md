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

search_bp coverage is in `test_search_bp_config.py`, `test_search_bp_decoder.py`,
`test_search_bp_storage.py` and `native/test_search_bp.cpp`. It covers scalar cycle
work, structural fixation/residual syndrome, fixed per-visit work, cold and ancestor
paths, direct CS0, deterministic reuse, all 14 schemas and saved inventory.
Current output-layout coverage is in `test_simple_results.py`: exact run/config
hash naming, physical-rate tags, the two-entry directory contract, human-readable
Parquet names, typed empty files, and a real one-shot end-to-end run. Historical
manifest/replay/report integration tests were moved to the OS trash during the
minimal-output migration; algorithm, native-boundary, circuit, schema, telemetry,
and dependency tests remain active.
`test_simulation_benchmark.py` verifies that the developer timing harness keeps
decode as one opaque phase, exercises the actual result writer, reports ranked
non-decoding phases, and leaves the configured scientific output root untouched.

SearchBP storage tests also compare native row/column telemetry exactly, validate
column-schema conversion, and run a two-worker spawn case whose four shots produce
four sample/result row groups despite physical batches of two. This exercises
pre-batch-completion streaming and bounded-queue parent writing.
