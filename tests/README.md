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
