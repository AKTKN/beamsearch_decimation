# Reusable verified analysis

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
is shared by the CLI and notebook, creates a new timestamped report, preserves source
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
analysis are deferred to Stages 4-5; v1 interpretation remains unchanged.

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
figures. The notebook consumes these outputs. See docs/hybrid_data.md for exact
schemas, denominators, settings and scientific interpretation limits.

The final E2E harness validates all report checksums and exact integer paired cost
totals, and executes the saved-data notebook. See docs/hybrid_acceptance.md. Current
analysis behavior and optional deferrals are recorded there; small smoke samples
remain insufficient for a scientific speed/accuracy conclusion.
