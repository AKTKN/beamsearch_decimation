# Hybrid migration — all six stages complete (2026-09-21)

Stage 6 finalizes the HSBP-ALG-1.0 / HSBP-EXP-1.0 implementation and its distribution.
The complete warm/cold/no-BP native service, paired v2 storage, historical v1 reader,
exact paired hypothesis analysis and saved-data consumers are implemented. Current
handoff: [docs/hybrid_acceptance.md](docs/hybrid_acceptance.md),
[docs/hybrid_native.md](docs/hybrid_native.md) and
[docs/hybrid_data.md](docs/hybrid_data.md). Historical status sections below are
preserved as dated evidence, including their then-outstanding stages.

Final review strengthened corrupt-data rejection for phase-result vocabulary,
terminal phase/stage agreement, OSD reach and prefix/OSD interval separation.
No native algorithm, circuit, DEM, logical map or dependency pin changed in Stage 6.
The source-restoration harness now checks the locked patch and every ldpc source,
rebuilds both opt-in bindings and a new project Release extension in a binary-free
isolated tree, then checks compiled/source identities and actual native decoding.
An initial harness-only identity-key error is retained in its failed log; the
corrected final restoration passed. The existing conda environment and other
installed dependencies were reused; this is not a new full-environment build.

Actual final validation in search_decimation:

| Command/check | Result and evidence under docs/test_results/ |
|---|---|
| `python -m pip install --no-build-isolation --no-deps -e .` | Built/installed the project Release extension; hybrid_stage_6_project_build.log |
| `scripts/build_dependencies.sh --check` | Passed source/runtime identities; hybrid_stage_6_dependencies.log |
| `python tests/check_hybrid_restoration.py` | Both bindings, project extension, source digests and 4/4 native tests passed; hybrid_stage_6_clean_restore_final.log |
| `python -m pytest -q` | **259 passed in 66.29 s**; hybrid_stage_6_final_pytest.log. Earlier pre-review suite: 256 passed, hybrid_stage_6_pytest.log |
| Selected pinned upstream command from docs/acceptance_report.md | **15 passed**, 6 upstream warnings; hybrid_stage_6_upstream.log |
| `python -m pytest -q tests/test_hybrid_storage.py` | 32 passed after phase-validation review; hybrid_stage_6_storage_review.log |
| Fresh CMake Release, Debug and ASan/UBSan builds + ctest | **4/4 each**; hybrid_stage_6_native_release/debug/sanitize.log |
| `python python_scripts/accept_hybrid.py --output assets/hybrid_stage_6_e2e` | Complete fresh-circuit six-case E2E acceptance; hybrid_stage_6_e2e.log and hybrid_stage_6_e2e_verification.json |
| Implementation diff whitespace check; companion-spec byte comparison | Passed. Supplied Markdown hard breaks and verbatim historical/build-log trailing spaces are preserved, so the unrestricted staged whitespace check reports those archived/input lines |

The final E2E harness executes the existing CLIs and preserves every command and
stdout/stderr under assets/hybrid_stage_6_e2e. Each case uses eight physical shots:
four surface d=3 and four BB72 R=6. Single-worker throughput, isolated latency,
two-worker throughput, replay and unprofiled replay each produce 24 paired decode
rows (hybrid, upstream CS0 and published beam). Warm/cold/no-BP ablations plus CS0
produce 32 rows. All measured base runs have 9 cycle and 26 phase rows; the ablation
run has 33 cycles and 77 phases. Unprofiled events are explicitly absent. All 12 BB
labels are verified. Single/multi/latency/replay/none scientific outputs agree
exactly with CPU caps disabled; measured scientific phase/cycle fields agree too.
The report has 12 paired groups and 65 checksummed outputs, and all six notebook
code cells execute without error. Exact integer cost identities pass. The actual
resolved manifest is [docs/examples/hybrid_manifest.json](docs/examples/hybrid_manifest.json).

Reproduce with a new directory:

```bash
conda activate search_decimation
python tests/check_hybrid_restoration.py
python -m pytest -q
python python_scripts/accept_hybrid.py --output assets/hybrid_acceptance_new
```

The production template retains surface d=5,7,9 and BB72, user-selected rates,
explicit budgets/seeds/analysis settings and optional disabled CS10. No production
sweep was launched. These smoke results establish software correctness and data
accounting, not a speed or accuracy advantage. Equal-LLR OSD ties remain platform
specific; prefix CPU caps are not full-service deadlines. Replay trials are not
independent LER observations. Optional heuristic caching/scan optimizations,
quantile-difference inference and instrumentation-overhead experiments remain
explicitly deferred. Native tests inject allocation failure safely; no actual
system-wide memory exhaustion is induced. Historical run snapshots stay immutable.

The user explicitly authorized final publication to the existing GitHub origin.
The complete migration is committed on the existing hybrid-decoder-stage1 topic
branch; main and the local ldpc screened-decimation-bp/upstream relationship are
preserved. Build products, local configs/notebooks and scientific run directories
remain ignored; reproducible source, templates, complete patches and evidence are
versioned.

---

# Hybrid migration — Stages 1–5 implemented (2026-09-21)

Stages 4 and 5 now connect the tested native hybrid to the existing paired runner,
versioned durable storage, saved-data hypothesis analysis, reports and notebook.
Work remains on the local `hybrid-decoder-stage1` branch. All prior status/log
sections below remain historical evidence; no historical scientific artifact was
rewritten. Current data/API documentation: [docs/hybrid_data.md](docs/hybrid_data.md).

Stage 4 preserves physical sampling, selected detector provenance, spawn workers,
parent-only writes, every enabled baseline on every paired shot and all 12 BB
observable labels. Native event export and truth labeling occur after the unchanged
outer service timer. Run/batch manifests are v2; tables are samples/1, decodes/2,
hybrid_rounds/1 and decoder_phases/1. The writer declares typed empty event tables
under phases and explicit omission under none. Invalid logical mismatch is null
in v2. Strict validators check pairing, event keys, counters, labels, phase order,
disjoint sums and signed residuals. Negative residuals are flagged and retained.
A BP exception may legitimately leave residual_after null. Clock/libc metadata,
model dimensions, effective settings and source/build provenance are preserved.
Historical v1 runs remain readable with validated nullable projection in memory.

Stage 5 reports stage/reach fractions, conditional valid accuracy, unconditional
block-failure contributions, cycle rescue/work/hints/caps, disjoint native costs,
paired discordance, and exact CPU/wall cost/error decomposition. Paired percentile
bootstrap supports shot or batch units with explicit seed/count/confidence. Replay
trials stay separate and cannot inflate independent LER sample size. No accuracy
margin means no equivalence/noninferiority claim. P99.9 is withheld without enough
tail support. Reports include warm/cold/no-BP comparisons, LER, CPU/wall ECDF and
survivor, stage, phase and paired-cost plots. The output-free notebook template
only consumes saved-data APIs. Local edited configs/notebooks remain untouched.

Actual validation in `search_decimation`:

| Command/check | Result / preserved log under docs/test_results/ |
|---|---|
| `python -m pytest -q` | 253 passed in 61.24 s; hybrid_stage_4_5_final_pytest.log. Earlier full run: 245 passed in 64.86 s, hybrid_stage_4_5_pytest.log |
| `python -m pytest -q tests/test_hybrid_storage.py tests/test_hybrid_analysis.py` after final event-policy guard | 49 passed in 15.37 s; hybrid_stage_4_5_final_boundary_tests.log |
| `python -m pytest -q tests/test_hybrid_analysis.py` after exact int64-before-float subtraction regression | 21 passed; hybrid_stage_5_integer_accounting_tests.log. Integer aggregate identities remain exact even above binary64's exact-integer range |
| `scripts/build_dependencies.sh --check` | Passed, hybrid_stage_4_5_dependencies.log; no native/external source changes or new native build were required in Stages 4–5 |
| `scripts/run_benchmark.sh config/hybrid_smoke.yaml.example -v` | 8 shots, 24 decodes, 9 cycles, 26 phases; hybrid_stage_4_smoke.log and *_path.txt |
| `scripts/run_benchmark.sh config/hybrid_latency.yaml.example -v` | Separate isolated one-worker run, same scientific results; hybrid_stage_4_latency.log and *_path.txt |
| `scripts/run_benchmark.sh config/hybrid_ablations.yaml.example -v` | 8 shots, 32 decodes, 33 cycles, 77 phases; hybrid_stage_4_ablations.log and *_path.txt |
| Two-worker run and replay using assets/hybrid_stage_4_configs/multi.yaml | 8 shots/24 decodes each; hybrid_stage_4_multi/replay.log and *_path.txt |
| Unprofiled replay using assets/hybrid_stage_4_configs/none.yaml | 8 shots/24 decodes; null durations and no event shards; hybrid_stage_4_none.log and *_path.txt |
| `python python_scripts/verify_benchmark.py SOURCE --compare OTHER` for multi/replay/latency/none | Every comparison: 8 samples and 24 non-timing decode results equal; phase/cycle scientific fields also equal when both measured; hybrid_stage_4_compare_*.log |
| `scripts/analyze_benchmark.sh config/hybrid_ablations.yaml.example --run ABLATION_RUN` | Complete report with 12 paired groups and 65 checksummed files; hybrid_stage_5_report.log, then final integer-accounting revision in hybrid_stage_5_final_report.log |
| `scripts/execute_notebook.sh config/hybrid_smoke.yaml.example --run SMOKE_RUN --notebook notebook/benchmark_analysis.ipynb.example --output assets/notebook/hybrid_stage_5_executed.ipynb` | All six code cells executed without error; hybrid_stage_5_notebook.log |
| `git diff --check` | Passed |

Accepted saved runs under assets/runs:

| Purpose | Directory |
|---|---|
| surface/BB throughput smoke | 20260921T044633.113050Z_465c7f27faf7 |
| isolated latency | 20260921T044637.532370Z_3e257ad8aaf3 |
| warm/cold/no-BP ablations + CS0 | 20260921T044642.224054Z_858c22c6915c |
| two workers | 20260921T044715.265104Z_681117be92f7 |
| saved-sample replay | 20260921T044722.027623Z_27e9c784f992 |
| profiling none replay | 20260921T044727.729919Z_65b8f27ea6ae |

`docs/test_results/hybrid_stage_4_5_verification.json` records paths, counts,
non-timing comparisons, all-12-BB checks, report checksums and executed-notebook
identity. The smoke hybrid visits zero syndrome, generated search goal, iterative
BP and OSD. Deterministic fixtures additionally cover transition BP, inconsistent
syndrome, invalid OSD and numerical failure, including null candidate labels and
exception accounting. Multi-table tests cover fourth-shard interruption, corrupt
or missing events, duplicate rows/foreign keys, and strict policy/version checks.
A self-contained constructed v1 fixture exercises historical false-on-invalid
labels before nullable projection; the preserved Stage 1 v1 artifact also loads.

Limits: these bounded shots validate software, not the scientific hypothesis.
No production sweep or performance/accuracy advantage is claimed. Timing trials
are not independent repeated LER evidence. A prefix CPU cap does not bound OSD or
full service latency. Bootstrap intervals are sample-dependent, and tiny/zero-event
samples are insufficient for scientific noninferiority conclusions. Optional paired
quantile-difference inference and profiling-overhead experiments are deferred.
OS allocation exhaustion is not deliberately induced by these tests. Stage 6's
full clean restoration/build and final migration acceptance remain separate work.
Later docs and boundary checks do not rewrite archived source snapshots.

---

# Hybrid migration — Stages 1–3 complete (2026-09-21)

Stages 2 and 3 are implemented on the existing local `hybrid-decoder-stage1`
branch. The pinned ldpc checkout retains `screened-decimation-bp` and its upstream
remote. Historical statuses below and their logs remain unchanged history.
The current API, ownership, numerical/telemetry conventions and implementation
limits are documented in [docs/hybrid_native.md](docs/hybrid_native.md).

Stage 2 adds the opt-in `ldpc.hybrid_bp` extension: an owned stateful parallel
min-sum session, immutable canonical graph/physical priors, finite replacement
hints, exact unclipped extrinsic arithmetic, and a direct pinned OSD-CS/order-zero
bridge. OSD receives the supplied signed LLRs and runs no BP. Ordinary upstream
BP-OSD/beam and the old reference_bp kernel are unchanged. All new sources,
including ignored bindings.cpp and the type stub, are recoverable from ldpc.patch;
the manifest, source archives and aggregate runtime/build hashes include every
authored and transitive input. Clean restoration compiled a new binding separately.

Stage 3 adds the C++ bounded correction search and complete hybrid state machine.
Search starts first, persists independent frontier/guidance heaps, uses canonical
branch partitions and the fractional residual-cover bound, and returns the first
generated goal. BP messages continue within each shot and reset between shots;
cold-BP and search-plus-OSD ablations are distinct. All paths validate original H,
predict A, and retain physical costs. Native CPU/wall summaries, per-cycle/phase
records, cap reasons and explicit numerical/resource failures are available, with
owned post-decode export. Full-recomputation reference and optimized paths preserve
exact decisions and counters. No residual-only pruning or beam truncation is used.

`DecoderAdapter(problem, Hybrid(...), profiling=True)` is callable now. Read
`DecodeResult.hybrid_summary`, then call `export_telemetry()` outside the service
timer and before another shot. Run/replay intentionally raises a precise Stage 4
storage error before creating a hybrid run: v2 schemas/events are not implemented
yet, and writing incomplete hybrid data through v1 would discard required evidence.
Existing baseline run/replay remains available. Per-node diagnostics are explicitly
unsupported; compact phase profiling is supported.

All validation below actually ran in the existing search_decimation environment:

| Command / check | Outcome and preserved log under docs/test_results/ |
|---|---|
| `(cd external_lib/ldpc && python setup_hybrid.py build_ext --inplace)` | Compiled opt-in binding; hybrid_stage_2_build.log and hybrid_stage_2_final_build.log |
| `python -m pytest -q tests/test_hybrid_bp.py` | 4 passed; independent edge-exclusion oracle, continuation/clipping, hints, empty shapes, reset; hybrid_stage_2_pytest.log |
| `g++ -std=c++17 -O2 -fno-fast-math -ffp-contract=off -I external_lib/ldpc/src_cpp tests/native/test_hybrid_bp.cpp -o /tmp/qec_test_hybrid_bp` then execute | 1,024 actual pinned CS0/OSD0 comparisons passed; hybrid_stage_2_native.log |
| `python -m pytest -q tests/test_provenance.py tests/test_hybrid_bp.py tests/test_upstream_regression.py` | 7 passed; patch restoration and 288 pristine BP-OSD comparisons included; hybrid_stage_2_regression.log |
| `python tests/check_hybrid_restoration.py` | Pristine temporary worktree + tracked patch, no old .so files, fresh opt-in compilation/digest/BP/OSD checks passed; hybrid_stage_2_clean_restore.log |
| `python -m pip install --no-build-isolation --no-deps -e .` | Recompiled/installed the project after native/CMake changes; final hybrid_stage_3_cmake_fix_build.log |
| `python -m pytest -q` | **205 passed in 50.93 s**; hybrid_stage_2_3_accepted_pytest.log |
| Focused suite after the final CMake path fix: test_config, test_hybrid_config, test_hybrid_bp, test_hybrid_search, test_hybrid_circuit_integration, test_provenance, test_decoders | **111 passed in 3.32 s**; hybrid_stage_3_cmake_fix_pytest.log |
| Release native ctest | **4/4 passed**; hybrid_stage_3_accepted_native_release.log |
| Debug native ctest | **4/4 passed**; hybrid_stage_3_accepted_native_debug.log |
| Debug + ASan/UBSan, leak detection enabled | **4/4 passed**; hybrid_stage_3_accepted_native_sanitize.log |
| `python python_scripts/audit_dependencies.py` and `scripts/build_dependencies.sh --check` | Passed after final audit metadata update; hybrid_stage_2_3_final_{audit,dependencies}.log |
| Native/source/clock identities | Verified and recorded in hybrid_stage_2_3_identities.json; native process/wall resolution reported as 1 ns on this platform |
| `git diff --check` | Passed for changed tracked files |

Native build configuration used `cmake -S . -B assets/build/hybrid-MODE
-DCMAKE_BUILD_TYPE=Release|Debug -DQEC_BUILD_TESTS=ON
-DPython_EXECUTABLE="$CONDA_PREFIX/bin/python"
-Dpybind11_DIR="$CONDA_PREFIX/lib/python3.12/site-packages/pybind11/share/cmake/pybind11"`.
The sanitize directory additionally used `-DQEC_SANITIZE=ON`. Final builds ran
`cmake --build assets/build/hybrid-MODE --target test_reference_bp test_search
test_hybrid_bp test_hybrid -j2` and `ctest --test-dir assets/build/hybrid-MODE
--output-on-failure`. Sanitizer ctest used `ASAN_OPTIONS=detect_leaks=1
UBSAN_OPTIONS=halt_on_error=1`. MODE is release, debug or sanitize; each has its
separate log and build directory. The editable extension was compiled in Release.

Stage 3 tests cover 6,912 exhaustive tiny matrix/syndrome/partial-assignment scores
and feasible-completion lower bounds, 350 independent full Python-oracle cases,
768 native reference/optimized cases, all terminal stages, zero-iteration BP
acceptance, deterministic node/time/cycle/depth limits, one-use hints, persisted
pools, cold/warm reuse, duplicate detector columns with different observables,
concurrent independent instances, numerical failure and injected allocation failure
with recovery. A bounded physical service check sampled four surface d=3 shots and
four BB72 R=6 shots at the existing software-check p=0.001, delivering every shot
to all three hybrid profiles and validating all 12 BB predictions. This was a
service test, not a v2 saved benchmark run or a logical-error performance study.

The manual fixed 80-check/180-mechanism search fixture produced 22,800 nodes across
100 trials in both paths: reference 87,122 us, optimized 38,931 us. Evidence is
hybrid_stage_3_performance.log and tests/native/benchmark_hybrid_search.cpp. This
uncontrolled-host development measurement excludes BP/OSD and is not a claim about
physical-code latency or accuracy. Further optional heuristic caching is deferred;
production currently recomputes active-column counts per node with reusable buffers.

Two intermediate issues are preserved in the logs. An initial full-suite attempt
recorded two pipeline identity failures after an adapter edit during live snapshot
runs; reruns with unchanged source passed (204, then 205 tests after counter tests).
Final incremental native rebuilding exposed four old relative CMake SHA256 paths
that failed from build directories. They now use absolute source paths; all three
incremental builds and the focused source/runtime suite passed afterward. Failed
attempt logs were retained rather than rewritten.

Remaining authorized migration stages, outside this request:

- Stage 4: carry native summaries/events through workers, compute outer service
  residuals and truth labels, implement v2 manifests/Arrow tables/atomic shards,
  preserve v1 reads and run complete paired/replay/spawn/latency workflows.
- Stage 5: paired cost/accuracy identities, bootstrap, stage analysis, reports and
  saved-data notebook execution.
- Stage 6: full fresh dependency/environment restoration and end-to-end acceptance.

No Stage 2/3 blocker remains. The new fork binding was clean-built, but no fresh
conda/full-dependency build is claimed. Upstream signed-LLR ties remain platform
specific. Prefix CPU caps do not bound OSD/full service. No production sweep,
publication or hosted fork was performed, and no scientific superiority is claimed.

---

# Hybrid migration — Stage 1 complete (2026-09-21)

Implemented on local branch `hybrid-decoder-stage1`. The historical stages 1-7
report below is preserved as history; it is not evidence of hybrid implementation.
The two supplied normative specifications are copied byte-for-byte into docs/.
See [the implementation map and decisions](docs/hybrid_migration.md).

Stage 1 adds strict nested HSBP-ALG-1.0 configuration, explicit warm, cold-BP and
search-plus-OSD profiles, finite numeric/resource validation, scalar/list budgets
resolved to explicit lists in JSON, and distinct algorithm/configuration identities.
The actual upstream `bposd_ms30_cs0` baseline is callable and correctly labeled;
CS10, screened_reference and published beam behavior remain preserved. Dispatch is
explicit and unknown kinds never fall through to beam. Enabled hybrid configurations
raise NotImplementedError before numerical imports, circuit work or run creation.
Hybrid execution is deliberately unavailable until Stage 3.

Added missing-only setup templates for hybrid smoke, ablations, user-rate production,
and runnable CS0 baseline smoke. Existing local configs/rates/sweeps/symlinks are
preserved. Production rates remain empty until supplied by the user. Provenance now
captures source .example templates, and docs define worker/model/session ownership,
non-reentrancy, shot resets, telemetry boundaries and exact future source/hash paths.
A v1/v2 mismatch-label convention difference is explicitly recorded for Stage 4.

Validation actually run in `search_decimation` (activate before these commands):

| Command | Result / evidence |
|---|---|
| `scripts/setup_local_files.sh` | Created missing local inputs; separate temporary setup tests preserved local edits and dangling symlinks across two invocations |
| `python -m pytest -q tests/test_hybrid_config.py tests/test_config.py tests/test_decoders.py` | 87 passed in 1.50 s; hybrid_stage_1_focused.log (before final label/archive/fallback additions) |
| `scripts/build_dependencies.sh --check` | Passed; hybrid_stage_1_dependencies.log |
| `python -m pip install --no-build-isolation --no-deps -e .` | Compiled/installed project extension successfully; hybrid_stage_1_build.log |
| `python -m pytest -q` | Initial 183 passed in 46.15 s; final **184 passed in 50.07 s** after review additions; hybrid_stage_1_pytest.log and hybrid_stage_1_final_pytest.log |
| `scripts/run_benchmark.sh config/bposd_cs0_smoke.yaml --verbose` | Complete isolated one-worker surface d=3 + BB72 R=6 software check; 8 shots, 24 CS0/CS10/beam rows, 4 paired batches; hybrid_stage_1_cs0_smoke.log |
| `python python_scripts/verify_benchmark.py assets/runs/20260921T031308.480482Z_694984c065d3` | Integrity validation passed; hybrid_stage_1_verification.log |
| `analysis.io.load_run` plus count/label assertions | 8 samples/24 decodes, all 12 BB observable labels; normative copies byte-identical; same verification log |
| `git diff --check` | Passed for edited tracked files; supplied normative Markdown copied without rewriting its formatting |

All new logs are in docs/test_results/. The bounded run path is also recorded in
hybrid_stage_1_cs0_path.txt. Regression coverage includes direct CS0-versus-upstream
outputs, forced BP failure followed by valid CS0, shot reuse, legacy parsing,
source archive templates, pristine ignored-binding restoration, existing complete
search/BP oracles, serial/spawn/replay pairing and analysis. No dependency source,
patch, pin or native algorithm was changed; manifest regeneration was unnecessary.
No new fresh dependency build or sanitizer run was performed in this stage.

Remaining work is intentionally outside this request:

- Stage 2: audited fork stateful min-sum and true OSD-only bridge, independent
  numerical oracles, compiled APIs, transitive hashes and clean patch restoration.
- Stage 3: native bounded search, persistent hybrid state machine, compact telemetry,
  native safety/performance checks and callable hybrid adapter.
- Stage 4: worker/event integration, CPU/wall accounting, manifest/schema v2 with
  historical v1 reading, atomic event tables and paired surface/BB/replay tests.
- Stage 5: paired cost/accuracy hypotheses, bootstrap, reports and saved-data notebook.
- Stage 6: clean restoration/build and full end-to-end/native acceptance/handoff.

No Stage 1 blocker remains. The next prerequisite is the Stage 2 fork API; there is
no hybrid kernel, OSD-only fallback or new event table yet. This smoke run validates
software only and establishes no performance advantage. No production sweep ran.

---

# Implementation status — stages 1–7 complete

Git distribution maintenance (2026-09-21): initialized the parent Git repository
on main for public publication to AKTKN/beamsearch_decimation. Working YAML and
notebooks, scientific artifacts, mutable reports, dependency checkouts and caches
are ignored. Portable .example templates and setup_local_files.sh restore missing
local inputs without replacing edits. Existing local experiments are preserved.
Native implementation and dependency sources/builds are unchanged.

Validation in search_decimation: scripts/build_dependencies.sh --check passed;
python -m pytest -q: **121 passed in 49.57 s**. Logs are
docs/test_results/git_distribution_{dependencies,pytest}.log. A temporary export
of tracked files validated setup twice, preservation of a local edit, all eight
runnable configuration templates, and the output-free notebook schema. Git
inventory checks found no working YAML/notebooks, data, binaries or gitlinks;
the authored binding remains in the locked ldpc patch. No new clean native rebuild
or production sweep was performed. Historical files were not rewritten.
The initial full-tree whitespace check flags preserved specification Markdown,
upstream patch bytes, historical logs and a reference file; those bytes are retained.

Latest maintenance: simulation and replay now accept `-v` / `--verbose`. Flushed
parent-only stderr messages show preparation, planned counts, committed-batch percent
and physical-shot totals, elapsed run time, verification and completion/failure.
Default output remains quiet; stdout remains the final run path. No YAML or scientific
parameter changes are needed. Progress updates once per committed batch, outside
per-shot decode timers. Python API: run_benchmark(..., verbose=True).

Validation: `python -m pytest -q` in search_decimation: **121 passed in 48.75 s**.
Regressions cover default quiet output, serial/spawn/replay scientific equality,
replay's actual source totals and failure progress. The command
`scripts/run_benchmark.sh config/stage5_validation.yaml --verbose` completed all four
code instances with two workers, 16 samples, 48 decode rows and eight committed
batches; verify_benchmark.py confirmed saved integrity. Evidence is in
docs/test_results/verbose_pytest.log, verbose_smoke.log and verbose_smoke_path.txt.
The clean-build acceptance results below remain historical evidence for stages 1–7.

Implemented and accepted on 21 September 2026 (Asia/Tokyo), using search_decimation.
No required stage remains unfinished, and no production sweep was run. Historical
Stage 1–3 and Stage 4–5 statuses remain under docs/test_results/.

Stages 1–5 provide physical surface d=5,7,9 and BB [[72,12,6]] Z-memory circuits,
R=d, circuit noise, verified Z-check projection and all BB logical observables;
canonical undecomposed DEMs; the opt-in forked native flooding BP; project C++ static-U
exhaustive screened search; actual unchanged BP-OSD/beam adapters; paired deterministic
serial/spawn execution, complete-service CPU/wall timing, strict Parquet, source
archives, incomplete committed subsets and saved-sample replay.

Stage 6 adds installed analysis modules for validated manifest/shard loading and
selection, summed failure components, Wilson intervals, exact descriptive timing
quantiles, ECDF/survival plots, explicit zero/tail handling, protected grouping,
checksummed reports and a successfully executed notebook. Documentation now covers
all YAML fields, schema, timing, fork maintenance, extension points and traceability.

Stage 7 built all required native dependencies and the optimized package in a new
conda prefix with independent pinned Git checkouts. The clean build exposed an ignored
authored bindings.cpp omitted from the ldpc patch. Audit/export/restoration and source
archives now preserve it; pristine-worktree byte restoration is regression-tested.
Ordinary BP-OSD and published beam kernels were not changed.

| Final verification | Outcome |
|---|---|
| Working environment `python -m pytest -q` | 117 passed in 27.82 s |
| Fresh environment `python -m pytest -q` | 117 passed in 28.52 s |
| Selected pinned upstream regressions | 15 passed; 6 expected legacy/OpenMP warnings |
| Pristine BP-OSD comparisons / complete-search oracle comparisons | 288 / 560, included in suite |
| Native Debug / ASan+UBSan | 2/2 passed each |
| Dependency/source/native import checks and pip check | Passed; all clean imports belong to the new workspace/prefix |
| Full 32-shot surface5/7/9 + BB72 smoke | 128 samples / 384 decoder rows in each of four runs |
| One/two/four-worker and isolated comparison | Exact physical samples and all shared scientific decoder outputs |
| Saved-sample replay with screened K=4 added | 128 samples / 512 decoder rows; 384 shared rows identical |
| Analysis and executed notebook | Complete PNG/PDF/JSON export; 5 notebook code cells executed |
| Production template | Expected validation failure before creating a run |

Exact argv/cwd/logs, versions, pins, native identities, run paths and comparisons are
in docs/test_results/stage_6_7_summary.json and docs/acceptance_report.md. Commands:

```bash
conda activate search_decimation
scripts/build_dependencies.sh --check
python -m pytest -q
scripts/run_benchmark.sh config/smoke.yaml
scripts/run_benchmark.sh config/latency_smoke.yaml
scripts/analyze_benchmark.sh config/smoke.yaml --run /path/to/run
scripts/replay_samples.sh /path/to/run config/decoder_sweep.yaml
scripts/execute_notebook.sh config/smoke.yaml --run /path/to/run --output assets/notebook/new.ipynb
```

Edit noise.rates or noise.sweep and decoders for user-selected experiments; sampling
and worker controls are also YAML. Outputs default to assets/runs and assets/analysis;
clean acceptance outputs are under assets/acceptance/20260920T223215Z_1c9e1644/.
The main environment remains available; the fresh prefix is preserved independently.

There is no unresolved required implementation blocker. Smoke data validate software,
not decoder superiority or extreme-tail precision. BB uses qLDPC edge coloring, not
the paper's optimized seven-layer schedule; published distance six is no circuit-distance
proof. Reference search allocates residual graphs per candidate and uses literal
exclusion operations; no latency advantage is claimed. Unavailable baseline counters
remain null. Host activity is not controlled by worker/thread settings. Exact resampling
requires the fixed environment and batch plan; stored samples support exact replay.
In-place resume and streaming/out-of-core analysis are not implemented. At the original acceptance, the root had
no Git metadata and no code or hosted fork had been published. Original specification/reference
files remain unchanged.
