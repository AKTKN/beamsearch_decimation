# Current minimal results

Use `analysis.simple_search_bp.summarize_run(run)` for new runs: logical error,
complete wall latency and OSD-call fraction, grouped within one run/condition/
decoder/execution context. Both five-field `lpm_dp_results/1` and six-field
`search_bp_results/2` are supported; only the latter includes the direct-search
correction flag. No raw samples or internal event diagnostics are available. The
plotting API below reads current results directly and retains historical
wider-schema compatibility. The full report APIs remain historical consumers.

# Saved-data analysis

The current interactive workflow is
[`notebook/benchmark_analysis.ipynb`](../notebook/benchmark_analysis.ipynb) with
the direct readers in `analysis.benchmark_plots`:

```python
from analysis import (
    decoder_event_rate_table,
    plot_decode_time_histogram,
    plot_logical_error_rate,
    plot_mean_decode_time,
)

rate_figures = plot_logical_error_rate(
    RUN_PATH,
    codes=["surface", "bb72"],
    physical_rates=[0.002, 0.0025, 0.003],
    distances=None,
    decoders=["search_bp", "beam8"],
)
time_figures = plot_mean_decode_time(
    RUN_PATH,
    codes="bb72",
    distances=6,
    decoders=None,
    clock="wall",
)
histogram = plot_decode_time_histogram(
    RUN_PATH, code="bb72", physical_rate=0.002, distance=6, clock="wall",
)
rates = decoder_event_rate_table(RUN_PATH)
```

Each argument may be a scalar or sequence; `None` includes all values. Decoder
selection matches an exact saved ID, name, or profile. The run must use the current
minimal `config_resolved.json` plus `data/` layout. For current runs the module
gets condition and decoder labels from resolved config and projects only required
columns from each `*_results.parquet`; it does not read samples or telemetry.
Historical layouts continue through their existing companion-file readers.

Current SEARCH-BP and LPM-DP logical errors use the contract-defined saved boolean:
decoder failure OR logical mismatch. Historical wide rows retain their explicit
recomputation. The
point denominator is the number of physical shots and the default shaded band is a
95% two-sided Wilson interval. Mean wall service time uses every shot, including
failures. Current data do not save CPU time, so `clock="cpu"` raises instead of
substituting another timer. Since a Wilson interval has no
definition for continuous durations, timing shading is a 95% Student-t interval
for the arithmetic mean.

The histogram API requires one code and physical rate. Distance is required for
the topological surface code and whenever selection would otherwise leave multiple
conditions. Times are shown in microseconds, one decoder per subplot, with mean,
p95, and p99 vertical lines. The event-rate API returns a pandas DataFrame indexed
by `(code, distance, physical_rate)`, with `(decoder, metric)` columns and rate
values in the cells. Current rows expose `osd_call_rate` for every decoder over
nonnull saved flags. SEARCH-BP results/2 additionally exposes
`correction_by_search_rate`; LPM-DP does not synthesize this unavailable metric.
Historical layouts retain search-BP OSD reach and beam
nonconvergence interpretations. Storage IDs and execution metadata are not included
in the displayed table; exact known/unknown denominators remain in `summarize_run`.

Every code family gets a separate 3.4 x 2.55 inch figure at 300 dpi, intended for
one column in a two-column RevTeX document. Functions return newly owned live
Matplotlib `Figure` objects and write nothing. Notebook users can adjust
`figure.axes[0]` and save in their desired format. The current notebook includes a
compact summary table and explicit output directory; the module itself performs no
automatic write, bootstrap, report generation or run merge.

## Historical manifest workflow

The remainder of this document describes the preserved legacy/report consumers;
it is not the workflow used by the current local benchmark notebook.

```bash
conda activate search_decimation
scripts/analyze_benchmark.sh config/analysis.yaml.example --run /path/to/run
scripts/analyze_benchmark.sh config/analysis.yaml.example --run /path/to/run --family bb72 --timing-mode isolated_latency
scripts/execute_notebook.sh config/analysis.yaml.example --run /path/to/run --output assets/notebook/smoke.ipynb
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
notebook/benchmark_analysis.ipynb selects explicit saved manifests and calls the
reader, basic statistics and plotting APIs directly. The execution CLI uses the active interpreter with a temporary
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

## Consumer migration and legacy

Use analysis-only config/analysis.yaml.example for saved-data work. Current CLIs
do not accept simulation YAML; simulation configuration contains no analysis
settings. See [analysis_migration.md](analysis_migration.md) for the independent
settings API, exact faster bootstrap, runtime provenance, progress, notebook kernel
selection and the preserved analysis.legacy entry points.

## Lightweight notebook workflow (2026-09-21)

The maintained and local interactive notebooks now call `load_run`/`select_records`,
`aggregate_failures`, `aggregate_timings`, `plot_failure_rates` and `plot_timings`
directly, in separate cells. They retain verified saved-data loading, protected
groups, Wilson intervals, conditional denominators and failed-shot timings.
The plot cell reuses in-memory data and exports only selected PNG/PDF figures to a
new `notebook_plots_*` directory. Summary dictionaries remain in memory.
No `create_report`, bootstrap, hybrid stage statistics or paired hypothesis analysis
is invoked by the notebook. The full-report CLI/API remains available separately.
Validation/loading and large figure sets still have costs; no out-of-core loading
or performance claim is introduced. Local CONFIG_PATH/RUN_PATHS values are retained.

### Local on-demand override (2026-09-21)

The user's subsequent instruction removes even integrity validation from the local
`notebook/benchmark_analysis.ipynb`. Its independent plot cells call
`analysis.quick_plots.plot_saved_data`, projecting only plot-specific decode
columns. Failure counts are grouped in Arrow; CPU/wall plots load only their own
clock. Configuration setup reads no run data. Available shards are trusted without
checksum, provenance, pairing, completeness or per-row consistency verification.
No samples, circuit matrices, event histories, bootstrap or timing strata are read
or computed. Separate run and scientific contexts and analytic Wilson intervals
remain. The `.ipynb.example` and full-report API retain verified behavior.
