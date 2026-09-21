# Stored schema and identities

The authoritative version-1 Arrow definitions are src/qec_bp_benchmark/storage/schema.py.
A sample is one physical shot; decodes are long-form rows keyed by run_id, instance_id,
sampling_id, shot_id and decoder_id. Samples are not duplicated per decoder. Parquet
schemas retain their qec_schema and bit_order metadata. The reader validates exact
schemas/nullability and paired row counts, not just filenames.

| Fields | Type / meaning |
|---|---|
| run_id, instance_id, sampling_id, decoder_id | Full content identities, never rounded labels |
| batch_id, shot_index, batch_seed | uint64; seed values above signed-int64 remain exact |
| shot_id | instance_id:sampling_id:shot_index, stable across saved-sample replay |
| family, distance, n, k_Z, rounds, physical_p | Physical code/noise labels; n is data-qubit count, not mechanism count |
| noise_id, model_hash, source_hash, config_hash | Exact profile/model/archived-source/resolved-config joins |
| num_detectors, detectors_packed | Selected detector width and little-bit-order bytes; zero high padding |
| actual_observables | Non-null bool vector of length k_Z, all 12 for BB72 |
| prediction | Nullable bool vector of length k_Z; null on declared or invalid output |
| status, native_status, syndrome_valid | Normalized SUCCESS/DECLARED_FAILURE/INVALID_OUTPUT; native stage detail; independent H parity validity |
| decoding_failure, valid_logical_mismatch, block_failure | Failure indicators per physical shot; components are disjoint |
| observable_mismatch | Nullable bool vector, null for failed decode |
| observable_total_failure | Non-null bool vector; every entry true for declared/invalid decode |
| cost | Nullable finite binary64 physical mechanism cost; null on failure |
| cpu_ns, wall_ns | Nonnegative int64 complete-service durations, including failed shots |
| timing_mode, concurrent_load, workers, native_threads, blas_threads, oversubscribed, profiling | Explicit execution/timing context; do not pool unlike values |
| initial_success, initial_iterations, post_iterations | Nullable native BP diagnostics; absent means unavailable |
| candidates, rejected, retained, bp_completions, successful_completions | Nullable uint64 screening counters; no invented baseline totals |
| selected_pattern | Nullable flattened increasing (original variable index, fixed bit) int64 list |
| correction_packed | Optional nullable canonical mechanism vector, width from saved H_shape.npy |
| diagnostics_json, phases_json | Optional finite JSON; phase clocks are nested wall durations, not additive independent services |

Screened initial-success shots have explicit zero search counts. BP-OSD exposes its
BP iteration count (known zero for the upstream zero-syndrome shortcut); its convergence
flag alone cannot reject a valid OSD output. Beam does not expose total search iterations,
so these fields remain null. A beam-exhausted native candidate can be syndrome-valid
but still yields DECLARED_FAILURE and no prediction. Unknown fields and missing paired
results are errors, not legitimate null decoder outputs.

Failure labels are defined in docs/benchmark_contract.md. Valid mismatch contribution
uses all physical shots; conditional mismatch uses only valid outputs, with a null rate
for zero denominator. BB has one 12-observable block trial per shot. Neither Parquet nor
analysis scales block failure by 12, multiplies sector rates by two, or divides measured
decode time by rounds to claim online latency.

Each instance contains original Stim/DEM bytes, H/A/prior arrays, detector/observable/
normalization maps, scientific metadata and an artifact manifest. Each batch manifest
lists both shard checksums/counts, offset/count/seed/sampling ID, decoder set and worker
setup/warmup/clock/thread diagnostics. Only a committed paired manifest makes shards
readable. A complete run must contain every expected batch/decoder and nonoverlapping
shot intervals. Interrupted orphan shards are not overwritten; start a new run or replay
its committed subset. In-place resume is not implemented.

Run provenance retains resolved/original configurations, exact source ZIP with a hash
index, tracked dirty patches and relevant untracked/ignored authored sources, dependency
locks and pinned upstream commits, actual native paths/hashes, compiler/build flags and
Python/CPU/affinity/thread metadata. The sampling plan specifies SeedSequence inputs,
stream tags, Stim version and call layout. Replay preserves raw selected detectors and
all truth outcomes while recording its new run/decoder/source identities and original
run manifest/config. Sample bits do not need to be resimulated for decoder comparisons.

Analysis outputs have separate version-1 JSON manifests, failures.json, timings.json,
decoder_profiles.json and checksummed PNG/PDF files. They retain grouping keys and
source-run manifest hashes. See docs/analysis.md for denominator and uncertainty rules.

## Hybrid v2 migration

New runs now use version-2 run/batch manifests and decodes/2 while samples/1 stays
unchanged. The v1 descriptions above remain the historical contract. In particular,
v1 false-on-invalid valid_logical_mismatch becomes nullable in decodes/2. See
[hybrid_data.md](hybrid_data.md) for exact Arrow field tables, native events,
nullability, clock/accounting conventions, atomic four-table commits and v1
in-memory projection. Historical Parquet bytes are never rewritten.
