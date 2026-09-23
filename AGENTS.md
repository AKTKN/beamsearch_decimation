# QEC BP benchmark

Current simulation output uses the minimal contract in docs/simulation_output.md.
New runs contain only `data/` and `config_resolved.json`, use
`YYYY_MM_DD_HH_MM_<config-hash-8>`, and prefix every Parquet filename with
`code_distance_rounds_rate_basis`. Do not restore run manifests, copied
circuit/matrix/source artifacts, inventories, summaries, file logs, final read-back
validation, or manifest-based replay to the active runner. Historical contracts,
readers, and evidence remain legacy-only.

Maintain the historical contract in prompts/codex_bp_benchmark_implementation_prompts.md
and docs/bp_decimation_screening_specification.md for screened_reference. Its seven
stages are accepted. The authorized hybrid migration follows
prompts/codex_hybrid_decoder_migration_prompts.md, normative
docs/hybrid_search_soft_bp_osd0_specification.md (HSBP-ALG-1.0), and
docs/hybrid_benchmark_data_and_hypothesis_specification.md (HSBP-EXP-1.0).
Hybrid Stages 1-6 are implemented: configuration, audited fork sessions, native
hybrid service, paired v2 telemetry/storage and saved-data hypothesis analysis.
Historical runs/readers preserve v1/v2. See docs/hybrid_native.md,
docs/hybrid_data.md, docs/hybrid_acceptance.md and STATUS.md for prior evidence.
The user explicitly authorized pushing the finalized migration to the
existing GitHub origin; do not force-push or change historical scientific artifacts.
Historical screened-reference/CS10 configs live in config/legacy/; top-level
config templates cover the hybrid and current baseline checks. The current runner
does not expose replay. Pre-migration consumers are preserved in analysis/legacy/,
python_scripts/legacy/, scripts/legacy/ and notebook/legacy/. Preserve relative
data/output destinations when moving configs.
Use the search_decimation conda environment for all programs. Production
physical rates remain user-supplied; do not launch a production sweep implicitly.

LPM-DP-BP-1.0 is complete through native Stage 3
(docs/lpm_dp_stage3.md). Its identity is kind `lpm_dp_bp`, profile/name
`lpm_dp_bp_v1`; no Python or simulator registration exists yet. The decoder uses
per-parent Stage-1 local-parity candidates, Stage-2 exact-message snapshots,
warm hard-decimation, main-note post-BP retention, bounded online child capture and
optional one-time terminal OSD-0. It does not use SEARCH-BP solve/guide search or
global admission. Reference execution keeps at most B old and B child snapshots
plus one session, with no raw-candidate-times-E/N allocation. Stage-3 evidence is
native Debug and ASan/UBSan 9/9, restoration 9/9, upstream BP 12, old-decoder
regressions 76; the full Python suite retains the documented legacy-config-only
331-pass/1-skip/1-failure baseline. Do not begin simulator integration without
Stage-4 authorization.

SEARCH-BP-2.0's active implementation/audit map is docs/search_bp_implementation.md.
The final pass preserves the root TeX and changes only search vector reservations;
decoder-only synthetic timings do not demonstrate a speedup or decoder advantage.
Do not conflate these measurements with complete-service simulation latency.
Final evidence: 330 Python tests passed, one unavailable historical-artifact skip;
12 upstream BP tests; native Debug and ASan/UBSan 7/7 each; clean fork/patch
restoration and paired serial/two-worker Surface d3 + BB72 d6 smoke passed.
SEARCH-BP-2.0 uses kind/profile/name `search_bp` and is integrated with the simulator
(Stage 5, docs/search_bp_stage5.md). Strict config maps directly to SearchBP2Settings,
including bp.scaling_factor; simulator q <= m applies to both local policies.
OSD-0, binary64 and no-fast-math are fixed (no fallback/numerics config sections).
New files are data/<condition>_results.parquet with the same five-field schema.
Workers transport minimal rows only; raw samples and wide telemetry remain legacy.
Stage 4 completes native Steps 5–7 as SearchBP2Decoder (docs/search_bp_stage4.md):
global dual-score admission, inherited decimated BP, R retention, fresh searches
each cycle and exactly one OSD-0 fallback. K_run is global across all parents.
The result has only valid/correction/prediction/physical_cost/osd_called. Final
posterior LLRs supply OSD, with fixed infinities mapped to signed DBL_MAX.
Stage 3 implements native Steps 1–4 (docs/search_bp_stage3.md), using the Stage-2
fork BP API. local_variable_policy defaults to refresh_descendant; fixed_root is
also supported. q counts all additional zero/one fixations. Search state is fresh
per parent expansion and must not persist across future recursive BP cycles.
Keep scoring/search/retention native; the Python adapter passes syndrome only.
Stage 2 supplies ldpc.hybrid_bp.DecimatedMinSumSession (docs/decimated_bp.md):
parallel min-sum, structural fixation, opaque snapshots, exact final check messages
and bounded clipped history.
Keep search/scoring/orchestration outside the fork. The existing hybrid, reference
and upstream kernels are unchanged; fixed posterior infinities are not OSD inputs.
Root `refined.tex` is normative; docs/search_bp_v2_design.md maps its equations
and records unresolved policies. Stage-3/4 policy resolutions are documented
separately; do not silently change them. Strict configs use search_bp_config/3 and explicit
algorithm_version SEARCH-BP-2.0. Native source identities are checked before decoder setup.
SEARCH-BP-1.0 sources/contracts/tests live in named legacy/search_bp_v1 areas and
are excluded from the active build/test suite. New results use search_bp_results/1:
shot_id, decoder_name, logical_error, latency_ns, osd_called. No raw samples or
telemetry tables. Use validate_config.py for dry runs; the example is smoke-sized, never a production sweep.

Directory responsibilities: src/ importable Python and native implementation;
python_scripts/ thin CLIs; scripts/ shell launchers; config/ strict YAML;
analysis/ direct minimal-layout readers/statistics plus legacy compatibility;
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
scripts/run_benchmark.sh config/legacy/stage5_validation.yaml
python python_scripts/validate_config.py config/search_bp.yaml.example
python -c "from analysis.simple_search_bp import summarize_run; print(summarize_run('SOURCE_RUN'))"
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
Run accepts -v/--verbose for parent-only stderr progress after saved batches.
Keep stdout as the final run path; logging must remain outside per-shot timers and
must not alter sample plans, decoder identities or scientific outputs.

Current analysis reads named Parquet data directly without manifests or final
validation and uses one block trial per physical shot. Preserve conditional
denominators, null diagnostics and failed-shot timings. Never pool incompatible
run/model/noise/decoder/sampling/execution contexts. Keep isolated/concurrent
timings separate; no division by R or 12. Label zero-event bounds and insufficient
tails. Legacy notebooks remain historical consumers.

Use new output directories after interruptions; there is no in-place resume. Update
module READMEs, affected documentation, traceability, source audit and STATUS.md with
actual commands/outcomes and genuine limits. Preserve historical test logs and
immutable run snapshots; later documentation does not rewrite archived source bytes.
