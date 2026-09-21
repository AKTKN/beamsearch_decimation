# Specification-to-implementation-to-test traceability

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
