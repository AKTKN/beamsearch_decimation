# Complete YAML interface

## SEARCH-BP-2.1

`kind`, `profile`, and `name` are `search_bp`. An explicit
`algorithm_version: SEARCH-BP-2.1` and `config_schema_version: search_bp_config/4`
are required. Old versions/keys fail validation. [Stage 5](search_bp_stage5.md)
lists every nested YAML field and its exact native mapping. Counts are strict
positive int32, k_keep <= k_run, q <= m for both local policies, W >= 1 and no
larger than either iteration budget. Clip/scoring/scaling values must be finite;
clip is positive and bounded against ring overflow, beta/lambda are nonnegative,
and bp.scaling_factor is in (0,1]. native_threads is fixed to 1. OSD-0 and
binary64/no-fast-math are fixed. Top-level `osd_fallback` is a strict boolean,
default true; false returns a declared failure after BP/search exhaustion without
calling OSD. Nested fallback/numerics sections are rejected.
`output.layout: minimal_results` uses `search_bp_results/2`; no telemetry keys
are accepted. `python python_scripts/validate_config.py config/search_bp.yaml.example`
validates without sampling. The enabled adapter calls the complete native decoder.

`load_config(path)` safely reads YAML, rejects duplicate/unknown keys, validates
parameters and resolves all paths relative to the YAML file. Config models are
frozen. `config.resolved()` returns finite JSON with explicit expanded rate/code
grids, resolved paths, algorithm defaults and audited fixed upstream properties.
An empty production grid is a validation error; no production rates are invented.

| Group | Fields and conventions |
|---|---|
| experiment | name, purpose, codes[{family,distances,rounds}], memory_basis=Z, sector=Z_checks, round_rule=distance. Omitted rounds means R=d; explicit rounds is labeled an override. Surface distances are odd >=3; bb72 distances must be [6]. |
| noise | profile=circuit_depolarizing; exactly one of rates or sweep. rates is unique, nonempty, finite [0,0.5]. sweep={kind:linear/log,start,stop,count} is endpoint-inclusive, count>=2, increasing, positive for log. multipliers has one_qubit,two_qubit,idle,reset,measurement, each nonnegative and products <=1. |
| circuit | surface_provider=stim, bb_provider=qldpc, surface_schedule=rotated_memory_z, bb_schedule=edge_coloring, edge_coloring_strategy=smallest_last, boundary=noisy_prepare_extract_readout, cache path. Other providers/schedules are rejected. |
| dem | decompose_errors=false, approximate_disjoint_errors=false by default (explicit true recorded), allow_gauge_detectors=false, sector_mapping=measurement_provenance, merge=none, normalization=remove_zero_reject_above_half. |
| decoders | List of unique named enabled instances. profile=screened_reference accepts T0,Tpost,history_window,M,q,K positive integers and 0<Lmax<=30; fixed sum_product/flooding/binary64 and disabled damping/warm_start/fallback. q<=min(M,n) is enforced at native preparation without silent reduction; the exactly empty normalized model is handled algebraically. |
| bposd profile | profile=bposd_ms30_cs10, max_iter=30, minimum_sum/parallel, ms_scaling_factor=1.0, OSD_CS, osd_order=10, omp_thread_count=1. Budgets may be changed in separately named instances. |
| beam profiles | profile=beam8 defaults max_rounds=10,beam_width=8,num_results=1,initial_iters=30,iters_per_round=20. beam32 defaults width=32,initial=40,per-round=30 and disabled. Only these five algorithm controls are supported. Generic bp_method is rejected. |
| sampling | shots_per_point, batch_size, master_seed, warmup_seed, warmup_count, store_raw_samples=false. Counts are positive except warmup may be zero. Physical sample identity excludes warmup. |
| execution | workers=4, start_method=spawn, max_pending=2*workers if omitted, worker_cache_size=2, native_threads=blas_threads=1, optional unique nonnegative CPU affinity. |
| timing | throughput or isolated_latency (requires one worker), both process_time_ns/perf_counter_ns timers, cyclic decoder order, profiling=none/phases. |
| output | root path, compression=zstd/snappy/none, shard_policy=paired_atomic_batch, retain_traces=false, retain_corrections=false. Minimal output adds compression_level and positive shots_per_flush (default 1024). No telemetry, corrections or raw samples are written. |

The preparation CLI consumes only circuit-related settings; run_benchmark.py executes
the full decoder comparison, and analyze_benchmark.py consumes saved datasets.
Decoder sweep examples deliver each physical shot to all enabled configurations.
Duplicate semantic decoder configurations are rejected even with distinct names.
See pipeline.md for timing, storage, replay and source-provenance details.

The independent analysis-only configuration's `analysis.quantiles` requests additional
quantiles beyond the mandatory median/p90/p95/p99/p99.9 summaries; duplicate values
are rejected. `analysis.plots` also accepts cpu_survival and wall_survival; duplicate
plot requests are rejected. `analysis.stratify_timing` defaults false and optionally
adds observed initial-BP/postprocessing/failure/unclassified-success strata.
`analysis.min_expected_tail_count` is a positive integer, default 10, used to flag
N(1-q) below that value. Neither passing the heuristic nor a smoke plot establishes
a performance advantage. Analysis input/output paths remain YAML-relative. Select
saved runs with --run; source experiment/noise fields do not trigger new simulations.


## Hybrid migration Stage 1

The complete new decoder field reference, budget resolution, ablation profiles,
numeric/resource limits and profiling scope are in [hybrid_migration.md](hybrid_migration.md).
The normative fragment is in HSBP-ALG-1.0 section 10. `kind` is distinct for hybrid;
legacy entries remain profile-discriminated and parse unchanged. The upstream
`bposd_ms30_cs0` profile fixes order zero; historical CS10 remains independently
configurable. Hybrid configurations now execute through DecoderAdapter. Runner/replay integration
requires Stage 4; see hybrid_native.md for the available service and event API.

## Hybrid analysis controls

`analysis.bootstrap_seed` is a nonnegative integer (default 20260921),
`bootstrap_count` a positive integer (default 2000), and `bootstrap_unit` is `shot`
or `batch`. The bootstrap keeps decoder outcomes paired and whole batches intact
when requested. `accuracy_margin_absolute` defaults to null, or accepts a finite
value in [0,1]. Its one-sided confidence bound criterion is documented in
hybrid_data.md. Existing `confidence` applies to rate and paired intervals.
`hybrid_latency.yaml.example` supplies a separate bounded isolated-latency check.

A complete, actual resolved smoke-run manifest is preserved in
[examples/hybrid_manifest.json](examples/hybrid_manifest.json). It includes explicit
cycle lists, all settings/seeds, independent model dimensions, table/event policy,
execution metadata, native identities and provenance hashes. Paths/identities refer
to that acceptance run and are illustrative for a different checkout.

## Analysis-only configuration

`analysis.load_analysis_config(path)` accepts the strict `analysis` envelope in
config/analysis.yaml.example without requiring any simulation grid or decoder.
It returns immutable analysis settings with YAML-relative paths resolved. Simulation
YAML intentionally contains no `analysis` section and is rejected by the analysis
loader. Current report/notebook CLIs default to the analysis-only template; legacy
CLIs retain their historical interfaces under `scripts/legacy/`.
See analysis_migration.md for compatibility, kernels, bootstrap and legacy paths.
