# Paired runner

`pipeline.run_benchmark(config_path, verbose=False)` returns an exclusively
created local-time `YYYY_MM_DD_HH_MM_<config-hash-8>` run directory. It contains
only `data/` and `config_resolved.json`; see `docs/simulation_output.md`. Parse/validate YAML and set
native/BLAS thread limits before numerical imports. The public import path itself
is numerical-library-free. Already-loaded BLAS pools are also limited through
threadpoolctl. Workers use spawn, never fork, with native objects constructed
locally. Affinity is optional and validated against the process's available CPUs;
workers exceeding available CPUs are explicitly labeled oversubscribed.

`plan.BatchTask` is frozen, metadata-only and picklable. task_stream is lazy.
Physical seeds are uint64 SeedSequence([master_seed, *little-endian uint32 words
of SHA256(instance_id + NUL + stream_tag), batch_id]). The tag is physical or
warmup. Shot ID is instance_id:sampling_id:shot_index. Batch size and pinned Stim
version belong to the sampling plan; changing decoders/workers/paths does not.
One compile_detector_sampler(seed).sample call samples the full physical circuit
per measured batch; selected_to_full projects its detectors. All logical truth
columns go to storage/evaluation, never to DecoderAdapter.decode.

A worker-local LRU holds at most worker_cache_size prepared problem/decoder groups.
Keys include instance, decoder configurations, trace and phase settings. Cache-hit
setup records report zero construction time; misses report CPU/wall setup ns.
Every batch uses a separate warmup seed/count; per-call native reset/cold start is
also used after warmup. Decoder IDs are sorted and rotated by shot_index, so YAML
list order cannot change which algorithm executes first on a given shot.

Each shot has CPU/wall clocks around the complete adapter decode. Truth comparison,
packing, setup, physical sampling, queues and I/O are outside that boundary. Optional
phase profiling is separately labeled and reports overlapping backend/subphase
wall clocks, not additive independent times. Zero/failure shots remain measured.
Throughput with >1 worker labels concurrent load. isolated_latency requires one
worker and one native/BLAS thread; host load outside this process is not controlled.
Timer overhead/resolution is recorded without per-shot subtraction.

The parent retains at most max_pending tasks (default 2*workers), consumes completion
order independently of task order, and is the sole Parquet writer. Exceptions cancel
pending futures where possible and propagate; no traceback/log file is added to the
result. There is no resume or manifest-based replay in the current runner.

`search_bp` uses a separate streaming path. A worker exports one completed shot as
dataset-specific columns and sends it through a bounded multiprocessing queue. A
single parent writer thread drains the queue while physical batches are still
running. Queue backpressure stops producers when storage falls behind. Serial runs
invoke the same writer sink synchronously. Worker futures contain only completion
metadata, not the shot telemetry already delivered to the sink. The parent owns a
separate bounded buffer per condition and coalesces exactly
`output.parquet.shots_per_flush` completed shots before appending one row group to
each nonempty dataset. The final partial group is flushed before writers close.

The developer-only `qec_bp_benchmark.benchmarking.simulation` entry point activates
coarse wall-clock scopes around this pipeline. `DecoderAdapter.decode` remains one
inclusive black-box phase. Ordinary runs do not activate these scopes, and the
measurements never enter the scientific result schema. The benchmark uses one
worker for additive accounting and temporary production-format Parquet output.

verbose=True prints flushed parent-only preparation, plan, saved-batch progress,
and completion/failure messages to stderr. Each line includes elapsed
run wall seconds; batch messages show completed/total batches, percent, physical
shots and code/distance/p. Counts advance only after rows are written. These messages stay outside
per-shot decode timers; elapsed run time includes setup and I/O. There is no per-shot
logging or heartbeat during a running batch. The CLI exposes -v/--verbose; stdout
remains the final run path. Verbosity is presentation only, not a YAML experiment setting.


## Hybrid Stages 4–5

Hybrid run/replay is enabled. Each worker exports owned native telemetry immediately
after the outer decode timers stop, labels it from the sampled truth, and returns
rounds/phases to the parent. Every enabled baseline still runs on every shot.
New output uses v2 manifests and decodes, with event policy and independent model
sizes recorded. Replays accept verified v1 or v2 sources and always create v2 in a
new directory. There is no in-place resume. See docs/hybrid_data.md.

The former replay-based acceptance command is historical evidence and is not part
of the current minimal-output runner.

Schema-version 3 runs buffer every frontier dataset per worker batch and publish
parent-owned shards through one committed inventory. V2 replay reads only saved
`shot_inputs`. Fixed-seed one- and two-worker runs must agree on physical and
non-timing algorithm rows; worker IDs and durations are execution metadata.
