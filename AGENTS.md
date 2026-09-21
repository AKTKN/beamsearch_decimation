# QEC BP benchmark

Maintain the historical contract in prompts/codex_bp_benchmark_implementation_prompts.md
and docs/bp_decimation_screening_specification.md for screened_reference. Its seven
stages are accepted. The authorized hybrid migration follows
prompts/codex_hybrid_decoder_migration_prompts.md, normative
docs/hybrid_search_soft_bp_osd0_specification.md (HSBP-ALG-1.0), and
docs/hybrid_benchmark_data_and_hypothesis_specification.md (HSBP-EXP-1.0).
Hybrid Stages 1-6 are implemented: configuration, audited fork sessions, native
hybrid service, paired v2 telemetry/storage and saved-data hypothesis analysis.
New runs write v2 while readers preserve v1. See docs/hybrid_native.md,
docs/hybrid_data.md, docs/hybrid_acceptance.md and STATUS.md for final evidence.
Use `python python_scripts/accept_hybrid.py --output NEW_DIRECTORY` for bounded E2E
acceptance. The user explicitly authorized pushing the finalized migration to the
existing GitHub origin; do not force-push or change historical scientific artifacts.
Use the search_decimation conda environment for all programs. Production
physical rates remain user-supplied; do not launch a production sweep implicitly.

Directory responsibilities: src/ importable Python and native implementation;
python_scripts/ thin CLIs; scripts/ shell launchers; config/ strict YAML;
analysis/ installed readers/statistics/plots/report/validation; notebook/ API consumers;
external_lib/ pinned sources, local ldpc development branch and dependency manifest;
simulation_data/ immutable scientific artifacts; assets/ mutable run/report outputs;
tests/ behavioral/native checks; docs/ contracts, integration and acceptance evidence;
reference_modules/ preserved examples, never installed.

Scientific invariants: sample physical circuits with both extraction sectors; select
Z-check records using verified provenance; preserve all 12 BB logical Z observables.
No truth enters decoder input. Retain DEM hyperedges and separator correlations.
The historical screened_reference uses mechanism priors, exact structural fixation,
cold-start flooding sum-product, binary64, specified clipping/ties, and no default
algorithm extensions. For that profile keep static U,
exhaustive fixed-q patterns, all-free-variable bounds, exact top K and every retained
completion. The new hybrid_search_soft_ms_osd0_v1 starts with bounded correction
search, preserves its frontier, replaces finite hints and continues parallel min-sum
edge messages within each shot, then calls direct native OSD-CS order zero. Search,
guidance and orchestration stay native. Reset all mutable sessions between shots;
they are not reentrant on one object. Search-only and cold-BP ablations have explicit
identities. Ordinary BP-OSD-CS10, BP-OSD-CS0 and the published beam baseline retain
upstream behavior. Never substitute kernels, relabel historical data or accept
ignored settings. Both algorithms retain physical costs and original H/A validation.

Use English, typed public APIs with documented shapes/ownership/errors, deterministic
ordering, focused independent tests and checked native boundaries. Keep all search,
per-iteration/per-pattern work and diagnostic formatting native. No fast-math.

Stable commands (activate search_decimation first):

```bash
scripts/build_dependencies.sh --check
python -m pip install --no-build-isolation --no-deps -e .
python -m pytest -q
scripts/run_benchmark.sh config/stage5_validation.yaml
scripts/run_benchmark.sh config/smoke.yaml
scripts/run_benchmark.sh config/latency_smoke.yaml
scripts/replay_samples.sh SOURCE_RUN config/decoder_sweep.yaml
scripts/analyze_benchmark.sh config/smoke.yaml --run SOURCE_RUN
python python_scripts/verify_benchmark.py SOURCE_RUN --compare OTHER_RUN
scripts/execute_notebook.sh config/smoke.yaml --run SOURCE_RUN --output assets/notebook/new.ipynb
```

Rebuild the project extension after native/search.hpp, native/module.cpp,
CMakeLists.txt or the fork BP header changes; runtime hashes reject stale binaries.
Hybrid rebuilds also require
`(cd external_lib/ldpc && python setup_hybrid.py build_ext --inplace)` after any
ldpc.hybrid_bp.source_files.SOURCE_FILES input changes; then audit dependencies and
rebuild the project extension. native_sources.HYBRID_PROJECT_FILES and CMake cover
all project hybrid headers/build inputs. Verify clean opt-in restoration with
`python tests/check_hybrid_restoration.py`. Build the reference binding explicitly with
`(cd external_lib/ldpc && python setup_reference.py build_ext --inplace)` after any
of its four hashed source/build files changes. Keep pybind11 2.11.1 for Stim and
build Stim extensions sequentially. After external-source/build changes regenerate
external_lib/manifest.lock.json and patches with python_scripts/audit_dependencies.py.
The patch/archive MUST include ignored src_python/ldpc/reference_bp/bindings.cpp;
its restoration is covered by tests/test_provenance.py. Preserve the upstream remote
and screened-decimation-bp branch. No hosted fork or publishing is required.

Fresh conda creation, complete dependency build, exact selected upstream tests and
native Debug/ASan/UBSan commands are in docs/build.md and docs/acceptance_report.md.
The accepted fresh build used new source clones and no previous native binaries or
circuit cache. Current evidence: 117 project tests, 15 upstream tests, 288 pristine
BP-OSD comparisons, 560 complete-search oracle comparisons, native 2/2 per build,
full all-four-code worker/mode/replay equality and executed analysis/notebook.

Subsequent verbosity maintenance has 121 passing project tests (see STATUS.md).
Run/replay accept -v/--verbose for parent-only stderr progress after committed batches.
Keep stdout as the final run path; logging must remain outside per-shot timers and
must not alter sample plans, decoder identities or scientific outputs.

Analysis must validate manifests/shards, sum counts and use one block trial per
physical shot. Preserve conditional denominators, null diagnostics and failed-shot
timings. Never pool incompatible run/model/noise/decoder/sampling/execution contexts
or interpret replayed shots as independent data. Keep isolated/concurrent timings
separate; no division by R or 12. Label zero-event bounds and insufficient tails.
Notebooks call analysis modules and contain no simulation/statistical implementation.

Use new output directories after interruptions; there is no in-place resume. Update
module READMEs, affected documentation, traceability, source audit and STATUS.md with
actual commands/outcomes and genuine limits. Preserve historical test logs and
immutable run snapshots; later documentation does not rewrite archived source bytes.
