# SEARCH-BP-2.1 simulator integration

The [active implementation and final audit](search_bp_implementation.md) now
provides the complete equation/function map, defaults, allocation audit and final
validation evidence. This document retains the integration and output details.

The existing Python simulator now dispatches `search_bp` to the complete
`_native.SearchBP2Decoder`. The adapter translates validated settings, passes only
the syndrome, independently validates original H/s, and computes the full original
A prediction and physical cost before returning. Truth comparison remains in the
worker after decode. No scoring, search, admission, retention or BP updates moved
to Python. No per-node/event dictionaries are constructed for SEARCH-BP.

Circuit providers/schedules, noise, detector selection/provenance, DEM handling,
physical sampling and true-observable generation are unchanged. Each sampled shot
still goes to every enabled decoder, using the same identity-based cyclic order,
seeds, warmup behavior and batch plan. BB retains all 12 logical observables.
Only decoder configuration/dispatch and transient/persisted result handling changed.
No production sweeps were run.

## Strict config and native mapping

The active schema is `search_bp_config/4` with explicit algorithm version
`SEARCH-BP-2.1` and kind/profile/name `search_bp`. The existing nested mathematical
names are retained; these are the complete tunable native algorithm fields:

| Mathematical/conceptual setting | YAML field | Native Settings field |
|---|---|---|
| initial_bp_iterations | bp.initial_iterations | initial_iterations |
| bp_iterations_per_candidate | bp.candidate_iterations | candidate_iterations |
| llr_window, W | bp.history_window | history_window |
| llr_clip, L_c | bp.average_llr_clip | history_clip |
| min_sum_scaling_factor | bp.scaling_factor | scaling_factor |
| top_checks, M | search.selected_checks | selected_checks |
| local_variables, m | search.local_variables | local_variables |
| max_decimation_depth, q | search.max_fixations | max_fixations |
| max_cycles | search.max_cycles | max_cycles |
| guide_lambda | search.guidance_strength | guidance_strength |
| ambiguity_beta | search.beta | beta |
| k_run | admission.k_run | k_run |
| k_keep | admission.k_keep | k_keep |
| user-requested local restriction | search.local_variable_policy | local_variable_policy |
| direct fallback enabled | osd_fallback | osd_fallback |

Counts are strict integers in [1, 2^31-1]. k_keep <= k_run, and **q <= m for both
policies**, as required for Stage 5. The broader native refresh_descendant test API
still supports q > m; simulator configuration intentionally rejects it. W cannot
exceed either BP iteration budget. Clip is finite positive and no larger than
DBL_MAX/(2W), preventing the existing ring accumulator from overflowing. Scaling
is finite in (0,1]. Beta/lambda are finite nonnegative. The policy remains
refresh_descendant by default, or fixed_root as explicitly requested in Stage 3.
`native_threads` is fixed to 1.

OSD-0, binary64 and no-fast-math are fixed implementation contracts. Top-level
`osd_fallback` defaults true; false returns failure after search/BP exhaustion.
The old nested `fallback`/`numerics` config sections are not exposed. Unknown
fields, SEARCH-BP-1.0 versions, old expansion/node/beam controls, telemetry,
retention heuristics, profiling and trace switches are rejected. No ignored
configuration keys are accepted. The fixed LLR-to-OSD convention remains the
user-approved Stage-4 rule: final signed posteriors, fixed infinities mapped to
signed DBL_MAX. Native source/hash checks run before preparing each decoder.

`config/search_bp.yaml.example` is a bounded smoke template; validate without
sampling using `python python_scripts/validate_config.py config/search_bp.yaml.example`.
Use `scripts/run_benchmark.sh CONFIG` for an explicitly chosen simulation config.
Rates in the example are software-validation inputs, not production recommendations.

## Exactly what is saved

Each new run contains only `config_resolved.json` and `data/`. Each physical
condition has one `<condition>_results.parquet`, with all enabled decoders' rows.
Filename prefixes keep code, distance, rounds, exact decimal rate and basis.
There are no condition/decoder metadata files, raw samples, corrections, predictions,
costs, statuses, telemetry, timing breakdowns, source/model/decoder hashes,
inventories, manifests, archives or end-of-run read-back validation.

Arrow metadata is `qec_schema=search_bp_results/2`:

| Field | Arrow type | Nullability |
|---|---|---|
| shot_id | string | nonnull |
| decoder_name | string | nonnull |
| logical_error | bool | nonnull |
| latency_ns | int64 | nonnull, nonnegative |
| osd_called | bool | nullable for an opaque baseline; exact nonnull bool for SEARCH-BP |
| correction_by_search | bool | exact nonnull bool for SEARCH-BP; null for baselines |

`logical_error = decoder failure OR any logical-observable mismatch`, using the
unchanged simulator `failure_labels` function. Failure includes declared failure
and invalid corrections. Failed shots remain in both error-rate and timing
statistics. `latency_ns` measures the entire `DecoderAdapter.decode` service with
perf_counter_ns, including conversion, native decode, final syndrome validation,
logical prediction and cost calculation. It excludes setup, warmup, sampling,
queueing, truth comparison, row conversion and I/O. Native `osd_called` and
`correction_by_search` are preserved
exactly. Existing baselines keep their exact flags; unknown backend usage may be
null, while non-OSD decoders report false.

Example directory tree (illustrative timestamp/hash):

```text
2026_09_22_14_05_12345678/
  config_resolved.json
  data/
    surface_d3_r3_p003_Z_results.parquet
    bb72_d6_r6_p003_Z_results.parquet
```

The worker now returns only these six scalar fields per decode, plus generic
batch/setup metadata outside the result rows. It no longer builds or transports
raw-sample rows or the old wide decode/event records. The writer owns one fixed
schema and one file per condition; its arbitrary-dataset/schema interface was
removed. Generic bounded batch futures, synchronous shot grouping and grouped
Parquet flushing remain. A failed run can retain closed partial files; there is
no resume, read-back pass or completeness claim.

Historical SEARCH-BP sampling/telemetry implementations remain under named
`legacy/search_bp_v1` source areas. Existing scientific files are not rewritten.

## Direct analysis

```python
from analysis.simple_search_bp import summarize_run
summaries = summarize_run('PATH_TO_RUN')
```

The function reads result files plus resolved config directly and groups by
condition and decoder within one run. It reports logical-error counts/rates and
the existing two-sided Wilson intervals; mean, median, p95/p99 service latency
including failures; and OSD fraction over known flags with the unknown count
separate. Existing standard timing summaries also report p90/p99.9 and tail-support
warnings. No telemetry is reconstructed. Earlier five-field `_logicalerror.parquet`
files remain readable, and historical wide schemas dispatch to their legacy reader.
Duplicate files for the same condition are rejected instead of silently pooling.
Smoke samples do not establish performance gains or tail precision.

## Changes and evidence

* `config.py` and the smoke template: availability, positive bounded counts,
  scaling, both-policy q constraint, fixed-setting removal.
* `decoders/__init__.py`: verified native dispatch/settings translation, syndrome-only
  decode, exact OSD flag and original H/A validation.
* `runner/worker.py`: unchanged sampling/paired scheduling, minimal result normalization.
  `runner/pipeline.py`: consume minimal rows and the fixed-schema writer.
* `storage/results.py`: one-schema/one-file writer, `_results.parquet` suffix;
  `storage/minimal.py` owns the six-field active contract and preserves historical
  five-field reads without rewriting them.
* `analysis/simple_search_bp.py`: direct new-file discovery, old-file compatibility,
  condition-file duplicate rejection and explicit p99 request.
* `tests/test_search_bp_stage5.py`: config rejection, exact mapping, truth-free
  boundaries, independent validation, failure timing/labels and flags, and paired
  single/spawn-worker Surface/BB smoke tests with BP-OSD-CS0 and beam8.
  Existing contract/storage tests now exercise the active binding and filename.

No native/fork rebuild or patch regeneration is needed: those source bytes are
unchanged. Source audit compares physics/DEM/sampling-plan/seed/failure-label bytes,
physical config ASTs and sampler/scheduling ASTs with the pre-integration versions.
Actual test/build-identity outcomes are recorded in STATUS.md and
`test_results/search_bp_stage5_*`.
