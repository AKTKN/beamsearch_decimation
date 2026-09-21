# Final clean-build acceptance — stages 1–7

Accepted 21 September 2026 (Asia/Tokyo). All required circuits and native decoders
are available, all final required checks passed, and the full finite end-to-end smoke
workflow completed. No production rates were selected or production sweep launched.

## Evidence and environment

The machine-readable [acceptance record](test_results/stage_6_7_summary.json) contains
actual argv/cwd, exit codes, durations, log checksums, source/native identities, versions,
row counts and comparisons. [Fresh dependency manifest](test_results/stage_7_dependency_manifest.json)
records the acceptance environment; external_lib/manifest.lock.json describes the
working environment. Run archives preserve the source bytes used at execution time;
later documentation changes do not rewrite those snapshots.

- Base: `assets/acceptance/20260920T223215Z_1c9e1644`.
- Independent source workspace: `assets/acceptance/20260920T223215Z_1c9e1644/workspace`.
- Fresh conda prefix: `assets/acceptance/20260920T223215Z_1c9e1644/envs/search_decimation`.
- Python: `3.12.14 | packaged by Anaconda, Inc. | (main, Aug 27 2026, 14:46:43) [GCC 14.3.0]`.
- Compiler: GNU C++ 11.4.0; Linux x86_64.
- Numerical stack: NumPy 2.5.3, SciPy 1.18.1, PyArrow 25.0.1.
- Native/provider packages: ldpc 2.4.1, Stim 1.16.0, qLDPC 0.3.3; beam identified by source commit.
- Build: pybind11 2.11.1, Cython 3.3.0, scikit-build-core 1.0.3.
- Analysis/notebook: Matplotlib 3.11.2, nbformat 5.11.1, nbclient 0.11.0, ipykernel 7.3.0.
- Tests: pytest 9.1.1.

| External source | Exact commit |
|---|---|
| BeamSearchDecoder | `084a475b05fb64308103317a1ce5a0c4b0be58aa` |
| BivariateBicycleCodes | `fa77e3333d3ec44c79d8f914dd24c040d1da471b` |
| Stim | `e2fc1eca7fd21684d433aa5f10f4504ea4860d07` |
| ldpc | `d3429964cd4ffe1abfc041c6ec8b8425cb174f40` |
| qLDPC | `53909112b25cff8d67d1a7528501d72c5a4a34e7` |
| stimbposd | `5ed95e415be245f93d5326c4898bd0182fe8f3bd` |

The ldpc fork remains local on screened-decimation-bp with upstream remote; no hosted
fork or publication was required. New Git clones checked out these commits, without
copying old native binaries, wheels, build trees or circuit cache. `--no-local` clones
used the available local repositories as source transport. Ordinary/pristine ldpc,
reference binding, beam, Stim and the project extension were compiled in the fresh
environment; qLDPC was installed from source. Other numerical/runtime packages were
installed from locked distributions, not claimed as locally source-compiled.

Actual project/reference/ldpc/beam/Stim/qLDPC imports were checked to be descendants
of this acceptance base. The record contains absolute module paths, SHA256 binary
and source hashes, and project/reference compiled identities. The project extension
is Release; reference flags are -O3 -std=c++17 -fno-fast-math -ffp-contract=off.
Standalone Debug/sanitizer test executables were separate and never benchmarked.

## Clean build and defect correction

The acceptance setup performed independent cloning and fresh prefix creation, then
executed the existing build helper directly. The concrete environment/build commands
were equivalent to the following, from the source workspace where indicated:

```bash
acceptance=/home/quantum_teresheys/workspace/beamsearch_decimation/assets/acceptance/20260920T223215Z_1c9e1644
/home/quantum_teresheys/anaconda3/bin/conda create --yes \
  --prefix "$acceptance/envs/search_decimation" \
  --file /home/quantum_teresheys/workspace/beamsearch_decimation/environment.conda.lock.txt
cd "$acceptance/workspace"
export PATH="$acceptance/envs/search_decimation/bin:$PATH"
export PYTHONNOUSERSITE=1 PIP_NO_CACHE_DIR=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
unset PYTHONPATH
python python_scripts/build_dependencies.py
python python_scripts/audit_dependencies.py
bash scripts/build_dependencies.sh --check
python -m pip check
```

[Environment creation log](../assets/acceptance/20260920T223215Z_1c9e1644/environment_setup.log) and
[successful complete source build log](../assets/acceptance/20260920T223215Z_1c9e1644/build_fixed.log) are retained.
The initial failed attempt is preserved as build_initial_missing_binding.log in the
same directory. Upstream ldpc ignores *.cpp under src_python, so the old patch omitted
our authored reference binding despite passing git apply --check. Audit now includes
explicitly hashed ignored files, restoration handles each missing opt-in file, and
provenance ZIPs preserve these bytes. A pristine-worktree regression applies the patch
and compares all four authored files. Rebuilding after this correction succeeded.
Ordinary BP-OSD and beam kernels were unchanged.

The build/preparation shell launchers now use the active interpreter consistently
with run/replay/analysis launchers, so a fresh prefix is honored without resolving
another environment by name. Their check/preparation commands were rerun successfully
under the fresh prefix; the working-environment build check also passed.

For future convenience, `scripts/clean_build.sh assets/acceptance` automates independent
copy/clone/prefix setup plus the same build/audit checks. Its CLI help was checked;
this acceptance used the directly executed setup/build procedure above rather than
claiming a second complete invocation of the new convenience wrapper.

## Tests and audits

```bash
python -m pytest -q
python -m pytest -q external_lib/ldpc/python_test/test_bp_decoder.py external_lib/ldpc/python_test/test_bp_decoder_input.py external_lib/ldpc/python_test/test_bp_serial.py external_lib/qLDPC/src/qldpc/circuits/memory/memory_test.py::test_memory_experiment external_lib/qLDPC/src/qldpc/circuits/memory/memory_test.py::test_errors external_lib/qLDPC/src/qldpc/circuits/memory/syndrome_measurement_test.py::test_syndrome_measurement_scheduling
cmake -S . -B build/debug -DQEC_BUILD_TESTS=ON -DCMAKE_BUILD_TYPE=Debug -Dpybind11_DIR="$(python -m pybind11 --cmakedir)"
cmake --build build/debug --target test_reference_bp test_search -j2
ctest --test-dir build/debug --output-on-failure
cmake -S . -B build/sanitize -DQEC_BUILD_TESTS=ON -DQEC_SANITIZE=ON -DCMAKE_BUILD_TYPE=Debug -Dpybind11_DIR="$(python -m pybind11 --cmakedir)"
cmake --build build/sanitize --target test_reference_bp test_search -j2
ctest --test-dir build/sanitize --output-on-failure
```

| Check | Final outcome |
|---|---|
| Working-environment project suite | 117 passed in 27.82 s |
| Fresh-environment project suite | 117 passed in 28.52 s |
| Selected pinned upstream regressions | 15 passed in 1.49 s; 6 expected legacy/OpenMP warnings |
| Ordinary fork BP-OSD versus pristine pinned installation | 288 exact comparisons, included in project suite |
| Complete screened C++ versus independent Python oracle | 560 comparisons, including reversed shot order, included in suite |
| Standalone Debug | 2/2 passed |
| Standalone ASan/UBSan | 2/2 passed |
| Intended native imports/build identity and pip check | Passed |

Logs are test_results/stage_7_project_tests.log, stage_7_upstream_tests.log,
stage_7_debug_test.log, stage_7_sanitize_test.log and stage_7_build_check.log;
main-environment tests are stage_6_7_main_pytest.log.

Audited native search uses one static terminal-history U, exhaustive fixed-q subsets
and assignments, structural removal of fixed columns, all-free-variable lower bounds,
exact top K ordering and every retained cold-start flooding completion. Final selection
uses physical cost and full-correction lexicographic ties. Tests check score bounds,
canonical ordering, contradictions, rescue/no-completion/multiple-success cases and
full reconstruction. Per-pattern search/diagnostic work stays C++. The actual separate
published beam binding receives only its five supported controls; no generic BP keyword
is silently forwarded. The original specification and six reference modules are preserved.

[Setting audit](configuration_audit.md) and [traceability](traceability.md) map the
remaining scope to code/tests: physical two-sector operations with verified selected
Z records; BB72 algebra and 12 observables; noiseless p=0; noise moments and boundaries;
undecomposed DEM hyperedges/separator correlations/logical-only columns; artifact hashes;
truth-free pairing; complete-service timers; effective threads/affinity/oversubscription;
strict null/schema/compression handling; short batches, atomic committed completeness,
exceptions and partial replay; source archives and dirty/ignored/worktree preservation.

Analysis tests use hand-counted unequal batches, known Wilson endpoints, zero valid
outputs, multiple dependent observables, missing diagnostics, exact interpolation/ties,
failed-shot timings, incompatible mixes, duplicates and corrupt/incomplete runs.
No pooling across protected identities occurs. Isolated and concurrent timings remain
separate. Visual inspection checked final CPU ECDF and BB failure figure labels/layout.

## Full end-to-end smoke

Each simulation uses p=0.001 with all five noise multipliers one, physical Stim circuit
sampling, Z-check decoder input, R=d and the same fixed sample plan: 32 shots per point,
batch size 16, master seed 20260920, separate warmup seed 20260921 and 4 warmup shots.
There are four points: surface d=5,7,9 (k_Z=1) and BB [[72,12,6]] (k_Z=12).

Enabled profiles are screened_reference (T0=Tpost=30, history=8, M=16, q=2, K=8,
Lmax=25), bposd_ms30_cs10 (30 min-sum, scale 1, order-10 OSD_CS), and beam8
(width 8, max_rounds=10, initial_iters=30, iters_per_round=20, num_results=1).
Replay adds screened K=4. The disabled beam32 example remains optional.

```bash
bash scripts/run_benchmark.sh config/smoke.yaml
bash scripts/run_benchmark.sh config/smoke_serial.yaml
bash scripts/run_benchmark.sh config/smoke_two_workers.yaml
bash scripts/run_benchmark.sh config/latency_smoke.yaml
```

Run folders are relative to the acceptance workspace's assets/runs/:

| Run | Folder | Samples | Decode rows |
|---|---|---:|---:|
| four_workers | `20260920T230054.456150Z_3404e1f3a42e` | 128 | 384 |
| isolated | `20260920T230120.596574Z_02d2c682f226` | 128 | 384 |
| one_worker | `20260920T230103.246777Z_2d7be50dfa48` | 128 | 384 |
| replay | `20260920T230131.887982Z_b289575349b7` | 128 | 512 |
| two_workers | `20260920T230112.149284Z_34f815f5c98b` | 128 | 384 |

Every run has eight complete paired batches. BB truth/prediction/mismatch vectors
retain dimension 12. One physical shot is one block trial, without division by 12,
a factor of two, or treating observables as independent trials. Comparisons checked
all 128 exact physical records and all 384 shared decoder result rows, including
statuses, syndrome validity, predictions, costs and available counters. Only execution
instrumentation and optional trace/correction retention fields are excluded.
Replay preserves the 128 original records and adds 128 decode rows; shared rows match.

Executed from the acceptance workspace (SOURCE and the variant paths above):

```bash
SOURCE=assets/runs/20260920T230054.456150Z_3404e1f3a42e
python python_scripts/verify_benchmark.py "$SOURCE" --compare assets/runs/20260920T230103.246777Z_2d7be50dfa48
python python_scripts/verify_benchmark.py "$SOURCE" --compare assets/runs/20260920T230112.149284Z_34f815f5c98b
python python_scripts/verify_benchmark.py "$SOURCE" --compare assets/runs/20260920T230120.596574Z_02d2c682f226
bash scripts/replay_samples.sh "$SOURCE" config/decoder_sweep.yaml
python python_scripts/verify_benchmark.py "$SOURCE" --compare assets/runs/20260920T230131.887982Z_b289575349b7 --allow-additional-decoders
bash scripts/analyze_benchmark.sh config/smoke.yaml --run "$SOURCE" --run assets/runs/20260920T230120.596574Z_02d2c682f226
bash scripts/execute_notebook.sh config/smoke.yaml --run "$SOURCE" --output assets/notebook/acceptance_smoke_executed.ipynb
# Expected validation error; verified no new run directory is created:
bash scripts/run_benchmark.sh config/production_template.yaml
```

All four simulation, replay, verification, analysis and notebook commands exited zero.
The production guard exited one as intended for its empty physical-rate grid, before
run creation. The machine-readable record contains the exact expanded argv used.

CLI [report manifest](../assets/acceptance/20260920T223215Z_1c9e1644/workspace/assets/analysis/20260920T230140.239323Z_42d33c5ead/manifest.json)
contains 768 selected rows, 24 failure groups, 48 timing groups and 24 figures in both
PNG/PDF (48 figure files). Throughput and isolated groups are separate. The
[executed notebook](../assets/acceptance/20260920T223215Z_1c9e1644/workspace/assets/notebook/acceptance_smoke_executed.ipynb) completed all five
code cells and exports its own timestamped report. Source notebook has no workstation
paths, decoder, sampler or duplicate statistical implementation. Stage 6 also executed
the notebook against the earlier Stage 5 saved output; its log is stage_6_notebook.log.

## Handoff and limits

For new experiments edit noise.rates **or** noise.sweep, decoders entries (unique names
and distinct parameters), sampling.shots_per_point/batch_size/seeds/warmup_count,
execution.workers/affinity and timing.mode in validated YAML. analysis fields control
confidence, additional quantiles, plots, optional path strata and tail threshold.
Outputs default to assets/runs, assets/analysis and the explicit notebook output path;
immutable reusable inputs are in simulation_data. Full commands are in README.md,
build.md, pipeline.md and analysis.md.

No required implementation blocker remains. These finite data validate software and
cannot establish decoder superiority or p99/p99.9 precision: N=32 gives expected tail
counts 0.32 and 0.032. Zero failures remain zero estimates with labeled Wilson upper
endpoints. CPU/wall plots measure complete offline blocks, never online round latency.
The qLDPC edge-coloring BB schedule is not the original optimized seven-layer schedule;
published distance six is not a circuit-distance proof. Reference candidate graph
allocation/literal exclusion operations are not optimized away or claimed faster.
Unavailable baseline counters remain null. Unrelated host activity is uncontrolled.
Bitwise Stim resampling requires identical pinned environment and batch layout; saved
samples give exact replay. In-place resume, streaming decoding and out-of-core analysis
are outside this implementation. The project root has no Git metadata; source archives
supply byte provenance. No commits or hosted forks were published.
