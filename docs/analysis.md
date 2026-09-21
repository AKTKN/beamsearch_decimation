# Loading, statistical analysis and notebooks

```bash
conda activate search_decimation
scripts/analyze_benchmark.sh config/smoke.yaml --run /path/to/run
scripts/analyze_benchmark.sh config/smoke.yaml --run /path/to/run --family bb72 --timing-mode isolated_latency
scripts/execute_notebook.sh config/smoke.yaml --run /path/to/run --output assets/notebook/smoke.ipynb
```

`--run` is repeatable. Without it, the analysis CLI discovers immediate run children
under analysis.input. Every run remains a separate group, including replays of the
same physical dataset. Additional selectors are --distance and --decoder-id (repeatable).
Use --allow-incomplete only to inspect checksum-verified committed subsets; those
results retain status incomplete. An artifact directory is not a run directory.
Reports are new UTC timestamp/nonce directories under analysis.output. Source runs
are read-only. There is no implicit choice of latest run or automatic pooling.

The reader verifies schema version, run/instance/config/decoder identity, physical
artifacts, source archive/environment checksums, paired sample/result counts, shot
intervals and Arrow null semantics. Missing shards and failed predictions are distinct:
a decoding failure is a real measured row with null prediction/cost; corruption or
missing required results raises an error. The loader materializes selected Arrow
tables; analysis is intended for explicitly selected finite datasets, not unlimited
in-memory discovery of a production archive.

`analysis.confidence` defaults to 0.95. Failure reports use two-sided Wilson score
intervals, with z from the standard normal distribution. One shot contributes one
Bernoulli block trial, including for BB with 12 logical Z observables. No factor of
two, division by 12, or independence assumption between observables is used.
Batch counts are summed; batch rates are never averaged. Reports contain:

- block failure / all shots;
- declared-or-invalid decoding failure / all shots;
- valid-output logical mismatch / all shots (a disjoint failure contribution);
- conditional mismatch / valid outputs (null rate and interval if the denominator is zero);
- per-observable mismatch/total-failure counts with their actual shot denominators.

For zero failures the point estimate remains exactly zero in JSON. On a logarithmic
figure the downward triangle marks only the upper endpoint of the two-sided Wilson
interval and is labeled 0/N. It is not an artificial positive estimate or a separately
calibrated one-sided 95% interval. Individual per-observable counts are descriptive;
no averaged per-observable interval is computed.

Timing summaries always include sample size, mean, median, p90, p95, p99, p99.9 and
maximum in integer-nanosecond input units. The quantile estimates use NumPy's explicit
linear interpolation; they may be fractional ns. analysis.quantiles adds requested
quantiles to the standard set. Each reports expected tail count N(1-q). Values below
analysis.min_expected_tail_count (default 10) are marked insufficient for a performance
claim; exceeding the threshold is not a guarantee of precise estimation. No timer
cost is subtracted. Failed/zero-syndrome shots remain included.

analysis.stratify_timing optionally adds initial-BP success, postprocessing, failure
and unclassified-success distributions to the all-shot summaries/plots. Missing
baseline diagnostics are never invented. CPU and wall clocks stay separate, as do
throughput/isolated mode, workers, native/BLAS limits, profiling and effective host/
affinity/library context. CPU scheduling contention is not converted into online
round latency: figures show complete-block milliseconds, without division by R.

analysis.plots accepts failure_rate, cpu_ecdf, wall_ecdf, cpu_survival and wall_survival.
Default exports are failure components plus CPU/wall ECDFs. Survival means P(T>t);
zero survival is retained, with no epsilon substitution. PNG and PDF artifacts,
failures.json, timings.json and full decoder_profiles.json are checksummed in the
analysis manifest. Curve legends retain decoder kernel/profile and budgets; different
kernels/budgets compare complete decoders, not screening alone.

The installed analysis package contains all loading/statistics/plotting logic.
notebook/benchmark_analysis.ipynb selects explicit saved manifests, calls create_report
and displays outputs. The execution CLI uses the active interpreter with a temporary
local IPC kernel and records selected paths in the executed notebook. Install the
locked notebook dependencies using the main build helper or the project notebook
extra. See notebook/README.md for interactive use.

Testing uses hand-computable count tables, known Wilson endpoints, exact interpolation
and empirical CDF examples, dependent BB observable fixtures, missing diagnostics,
duplicate/incompatible groups, incomplete/corrupt runs and real saved native output.
Small smoke data establish software behavior only; they cannot support decoder
superiority or reliable extreme-tail estimates.

## Hybrid paired hypothesis analysis

See [hybrid_data.md](hybrid_data.md) for the Stage 5 public APIs, bootstrap controls,
physical-trial/replay policy, four-term CPU/wall accounting and output inventory.
The report exports hybrid_stages.json and paired.json in addition to the existing
count/timing outputs. Noninferiority requires a supplied absolute margin; the
bootstrap criterion is reported explicitly. P99.9 is null below the configured
tail support threshold. Failed shots stay in timing distributions. Warm/cold/no-BP
ablations are compared using their distinct recorded decoder identities.
