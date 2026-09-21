# Paired runner

`pipeline.run_benchmark(config_path, replay_source=None, verbose=False)` returns an exclusively
created UTC timestamp + random suffix run directory. Parse/validate YAML and set
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
order independently of task order, and is the sole shard writer. Exceptions cancel
pending futures where possible, propagate and leave status incomplete plus traceback.
No resume support. Replay reads only checksum-verified committed pairs and copies
saved physical artifacts. The source's physical dataset is authoritative: replay
YAML selects decoders, execution, timing and output, not a new sample grid. A replay
of an incomplete run preserves holes and records its source status/manifest/config.

verbose=True prints flushed parent-only preparation, plan, committed-batch progress,
verification and completion/failure messages to stderr. Each line includes elapsed
run wall seconds; batch messages show completed/total batches, percent, physical
shots and code/distance/p. Counts advance only after paired shards and the manifest
are saved. Replay totals use the committed source dataset. These messages stay outside
per-shot decode timers; elapsed run time includes setup and I/O. There is no per-shot
logging or heartbeat during a running batch. The CLI exposes -v/--verbose; stdout
remains the final run path. Verbosity is presentation only, not a YAML experiment setting.
