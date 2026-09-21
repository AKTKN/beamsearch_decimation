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
