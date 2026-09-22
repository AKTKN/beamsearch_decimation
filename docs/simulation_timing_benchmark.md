> SEARCH-BP-1.0 timing evidence below is historical. SEARCH-BP-2.0 decoding
> is not implemented; the current timing harness can exercise baselines only.

# Simulation timing benchmark

`python_scripts/benchmark_simulation.py` measures the real simulation runner while
treating `DecoderAdapter.decode` as one opaque phase. It is an engineering tool,
not a scientific decoder-latency comparison.

The benchmark forces one worker and isolated-latency mode so wall-clock phases are
additive. It preserves the selected codes, rates, decoder settings, circuit cache,
sampling seeds, warmup count, output schema, compression, and telemetry settings.
`--shots` and `--batch-size` may bound the diagnostic workload. Scientific Parquet
files are written through the production path in a temporary directory and removed;
an optional JSON report is written outside the simulation run layout.

```bash
conda activate search_decimation
scripts/benchmark_simulation.sh config/bposd_cs0_smoke.yaml.example \
  --repeats 3 --shots 32 --batch-size 16 \
  --output assets/benchmarks/search_bp_simulation_timing.json
```

Measured worker phases are model setup, configured warmup, physical Stim sampling,
shot-input preparation, the opaque decode call, telemetry export, result
normalization/truth labeling, and thread-pool verification. Parent phases include
Arrow table conversion, Parquet writing, writer open/close, and batch bookkeeping.
Startup/import/artifact preparation is reported separately from steady batch work.

Instrumentation is activated only through the benchmark entry point. Ordinary
`run_benchmark` calls do not take the additional phase timestamps and no benchmark
fields enter scientific Parquet schemas. Use several repeats on an otherwise idle,
frequency-stable host. Do not compare reports with different configs, hardware,
thread settings, cache states, or telemetry policies.

## Current bounded result

The 2026-09-22 bounded measurement used two conditions, 32 shots per condition,
three enabled decoders, batches of 16, and three complete repeats. Median wall time
was 2386.514 ms, of which opaque decoding was 1516.827 ms (63.56%). Cached instance
preparation was 571.597 ms (23.95%); the first repeat was 1547.617 ms because it
included colder artifact/provider work.

Among measured steady non-decoding work, result normalization was the primary
bottleneck at 79.313 ms (51.9%). Arrow conversion was 27.963 ms (18.3%), Parquet
writing 24.209 ms (15.9%), per-batch thread-pool verification 11.519 ms (7.5%), and
shot-input preparation 3.887 ms (2.5%). Physical sampling was only 0.522 ms. The
saved evidence is `assets/benchmarks/search_bp_simulation_timing_2026_09_22.json`.

The strongest simulation-logic optimization targets are therefore:

1. Avoid constructing the generic legacy decode/telemetry rows for typed
   `search_bp` output; implemented by the subsequent shot-streaming migration.
2. Balance bounded shot groups against Arrow/Parquet call overhead. The current
   path coalesces `shots_per_flush` completed shots per condition without retaining
   an entire sampling batch in each worker future.
3. Validate numerical thread pools once at worker initialization or cache the
   invariant result instead of calling `threadpool_info()` after every batch.
4. Cache or lazily load condition preparation inputs when startup latency matters.

The figures above predate the shot-streaming migration and remain its baseline, not
current performance evidence. Re-measure after every change with identical inputs.

## Post-streaming measurement

The same bounded workload after the shot-streaming migration measured 2829.312 ms
end-to-end and 1462.458 ms in opaque decoding. Measured steady non-decoding work was
578.750 ms: Parquet writing 307.676 ms (53.2%), Arrow conversion 128.585 ms
(22.2%), result normalization 105.056 ms (18.2%), shot-input preparation 16.983 ms
(2.9%), and thread-pool verification 12.022 ms (2.1%). Evidence is
`assets/benchmarks/search_bp_simulation_timing_2026_09_22_streaming.json`.

This historical comparison exposed the expected memory/I/O tradeoff. Its measured
implementation converted each nonempty shot/dataset into a separate Parquet row
group. The current implementation instead coalesces a configurable bounded number
of shot chunks while retaining producer backpressure. The figures above predate
that coalescing change and are not current performance evidence.
