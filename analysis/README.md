# Active analysis

Use `analysis.simple_results.summarize_run(path)` for new
`benchmark_results/3` and previous `/2` runs. New runs report convergence,
logical error conditional on convergence, and AF-BP initial/first-transform
rescue counts; old runs return unavailable values for those statistics.
`analysis.plot_convergence_rate(path)` plots only new runs.
Use `analysis.list_run_conditions(path)` to enumerate and validate every saved
condition file before plotting. The active notebook uses this API to make one
latency histogram per condition, alongside logical-error, mean latency, and mean
total-iteration figures. See `notebook/README.md` for the runnable workflow.
The public `analysis` plotting functions draw saved logical-error, complete
latency, and mean total-iteration figures, with code/distance/rate/decoder
filters. Failed shots contribute to time and iteration summaries. Active
readers reject prior schemas; historical multi-schema plotting is available
through `analysis.legacy.benchmark_plots` and other old consumers under
`analysis/legacy/`. The sections below document historical contracts.

---

# Historical minimal analysis (legacy schemas)

For current minimal results, use `analysis.simple_search_bp.summarize_run(run)`
for detached statistics and the public `analysis.plot_*` functions for figures.
The plot readers consume `*_results.parquet` directly, with condition and decoder
labels from `config_resolved.json`. Both six-field `search_bp_results/2` and
five-field `lpm_dp_results/1` support logical-error rate, complete wall latency,
latency histograms and OSD-call rates. Only SEARCH-BP stores the additional
direct-search correction flag. CPU latency, failure components and internal decoder
events are absent and are not reconstructed.
It directly reads `<condition>_results.parquet` plus resolved config and reports
logical-error rate/Wilson bounds, mean/median/p95/p99 latency including failures,
and OSD fraction with known/unknown denominators, grouped by condition and decoder.
Earlier `_logicalerror.parquet` minimal files remain readable. No telemetry or
inventories are required. See docs/search_bp_stage5.md.

The plotting interfaces below support both current minimal layouts and preserve
earlier wide-layout consumers.

`analysis.benchmark_plots` is the notebook-facing analysis module. Its public
functions accept a minimal-layout run path and exact experiment selections:

- `plot_logical_error_rate` reads logical-result columns and returns one figure per
  code family. Current rows use the saved contract-defined logical-error boolean;
  historical rows reconstruct decoder failure OR logical mismatch. Shading is a
  two-sided Wilson interval over physical shots.
- `plot_mean_decode_time` reads complete service timings, including failed decodes,
  and returns one figure per code family. Shading is a Student-t interval for the
  mean because Wilson intervals are defined only for binomial proportions.
- `plot_decode_time_histogram` selects one code/rate/distance condition and returns
  one figure with a frequency subplot per decoder. Saved nanoseconds are displayed
  in microseconds; vertical lines mark the mean, p95, and p99.
- `decoder_event_rate_table` returns a pandas DataFrame whose row MultiIndex is
  `(code, distance, physical_rate)` and whose column MultiIndex is
  `(decoder, metric)`. Current cells contain OSD-call rates over known flags;
  SEARCH-BP results/2 also contains its direct-search rate, while LPM-DP does not
  infer that unavailable metric. Historical layouts retain search-BP OSD-reach and
  beam nonconvergence rates.

Both functions create 3.4 x 2.55 inch, 300 dpi figures suitable for one column of
a two-column RevTeX paper. They return live Matplotlib `Figure` objects and never
write output files. The caller can edit `figure.axes[0]` or call `figure.savefig`.
Current runs read resolved config and selected columns from `*_results.parquet`.
Historical runs read their condition/decoder companions and selected columns from
`*_logicalerror.parquet`. There is no run merging, bootstrap, telemetry load or
decoder execution.

The manifest-based modules described below are historical compatibility code;
their preserved implementation is also available under `analysis.legacy`.

## Historical verified analysis

This directory is an installed Python package (`import analysis`). `io.load_run`
checks run/artifact/provenance manifests, schemas, paired-shard checksums, counts,
non-overlapping shot intervals, all observable dimensions and run/config identities.
`discover_runs` lists immediate run directories, excluding incomplete runs by default.
`allow_incomplete=True` explicitly exposes committed subsets and labels them.
`select_records` filters family/distance/decoder/mode and rejects duplicate selected
run/shot/decoder keys. Loading materializes the selected Arrow tables in memory;
select finite datasets or one run at a time for larger campaigns.

`statistics.aggregate_failures` sums indicators over individual physical shots.
Protected groups include run, scientific instance, sampling plan, decoder identity,
noise/model hashes, mode, workers/threads, profiling, host/affinity/library context.
Runs and replays never pool silently. `summarize_failure_group` rejects incompatible
rows. Block uncertainty uses two-sided Wilson intervals and N physical shots, never
12N BB observables. Components use all shots; conditional mismatch uses valid outputs
and is null when none exist. Per-observable counts retain their shot denominators;
no average-per-observable independence claim is made.

`timing_statistics` reports mean, median, p90/p95/p99/p99.9/max and requested additional
quantiles in ns, using explicit linear interpolation. Every quantile includes N and
N(1-q), plus an insufficient-tail flag below min_expected_tail_count (default 10).
Passing that heuristic threshold does not establish precision. `aggregate_timings`
keeps CPU/wall/modes separate and optionally stratifies only observed path metadata;
missing upstream counters remain unclassified. Failed shots remain in all-shot timing.
`empirical_distribution` returns exact empirical CDF or P(T>t), preserving zero tails.

`plots` writes PNG/PDF figures per compatible code/noise/run/execution group. Failure
plots show zero estimates only as explicitly labeled Wilson upper endpoints on log
axes. CPU/wall plots show individual complete-block times in ms, never divided by R.
Legends retain native kernel/profile budgets, N and tail support. `report.create_report`
is used by the full-report CLI, creates a new timestamped report, preserves source
run manifest hashes and output checksums, and leaves status incomplete on error.

Analysis imports no decoder/provider modules, samples no circuit and changes no
source runs. See docs/analysis.md and tests/test_analysis.py.

`validation.compare_runs` requires identical stored physical detector/truth records
and every shared decoder's scientific result, including available search counters.
It ignores timing/instrumentation and optional trace/correction retention fields;
`allow_additional_decoders=True` permits an expanded decoder replay on the right.
Both inputs must first pass load_run integrity checks.

Hybrid Stage 1 adds honest plot labels for upstream `bposd_ms30_cs0` and preserves
CS10 labels with their actual iteration/order settings. Unknown profiles fail
explicitly rather than acquiring a beam label. Hybrid tables and hypothesis
analysis are implemented below; v1 interpretation remains unchanged.

## Hybrid APIs

`io.load_run` dispatches v1/v2 and returns validated hybrid_rounds/decoder_phases
Arrow tables. V1 absent hybrid fields project to null; invalid mismatch projects
to null after validation of historical labels. `hybrid.stage_statistics` reports
exit/reach, conditional accuracy, failure contributions, disjoint native costs and
per-cycle rescue/work/caps. `hybrid.paired_statistics` preserves protected contexts,
checks exact four-term CPU/wall accounting, and bootstraps paired shot or batch
observations. Each replay stays a separate dependent timing trial. `summarize_pair`
rejects mixed identities and flagged timing accounting. All units are ns.

Reports include hybrid_stages.json, paired.json and stage/cost/ablation PNG/PDF
figures. The notebook directly calls the basic readers, statistics and plotting APIs
without producing these detailed hybrid comparisons. See docs/hybrid_data.md for exact
schemas, denominators, settings and scientific interpretation limits.

The final E2E harness validates all report checksums and exact integer paired cost
totals, and executes the saved-data notebook. See docs/hybrid_acceptance.md. Current
analysis behavior and optional deferrals are recorded there; small smoke samples
remain insufficient for a scientific speed/accuracy conclusion.

## Current consumer and preserved legacy

`load_analysis_config` accepts only strict analysis-only YAML; simulation settings
are not part of that interface. `analysis_runtime` identifies the active interpreter
and consumer source hashes. `create_report` takes
an optional progress callback and records consumer provenance in its manifest.
`bootstrap.PairedBootstrap` reuses exact integer unit totals with legacy-compatible
RNG draws, including unequal batches and an overflow-safe Python-integer fallback.

The previous complete implementation is byte-preserved in `analysis.legacy`, with
snapshot hashes and separate legacy consumers. See docs/analysis_migration.md.

## Trusted on-demand plotting

`quick_plots.plot_saved_data` supports the explicitly requested local interactive
workflow without integrity verification. Each call reads run/instance JSON for
labels and grouping and projects only the required decode Parquet columns, one
instance at a time. It never reads sample, event, source archive or circuit files.
Failure plots aggregate flags with Arrow; timing plots read only the selected
clock and display all shots. Available decode shards are trusted directly,
including uncommitted shards; this API is not the verified report reader.
Scientific/run/decoder/execution grouping and physical-shot denominators remain.
No bootstrap, hybrid details or shared all-data cache is used.

## Current minimal results

`simple_search_bp.summarize_run` reads the result file directly and
obtains condition/decoder/execution context from config_resolved.json. It reports
logical error over all physical shots, failure-inclusive wall latency, and exact
OSD call counts over known flags with unknown counts separate. It never merges
runs. Old 14-dataset and standard-file reads dispatch to
`legacy/search_bp_v1/simple_search_bp.py`. Historical plotting/report APIs above
still consume their original schemas; use the minimal reader for new results.
