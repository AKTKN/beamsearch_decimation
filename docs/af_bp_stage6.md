# AF-BP Stage 6: active benchmark integration

The active registry contains `af_bp`, `relay_bp`, `beam8`, and ordinary
`bposd`. They receive the same selected-detector syndrome for each physical
shot. Stage 6 changed decoder registration, strict config, active result
metadata, and figure routing. It did not change circuit/noise/DEM preparation,
physical sampling, seed derivation, detector projection, truth comparison,
worker scheduling, or the complete `DecoderAdapter.decode` timing boundary.
No native AF-BP, Relay, Beam8, or BP-OSD scientific kernel was changed.

## Configuration and decoder boundary

`config.AFBP` exposes the complete Stage-4 service options: history and
residual failure weights, U selection, factorization policy and count,
graph rounds, BP variant and budgets, initial-parallel policy, Min-Sum scaling,
serial order, qDither phase/chain/mixing/RSF/handoff settings, parity-LLR
clip, and deterministic seed policy. The active adapter maps these names once
to `af_bp_service.AFBPConfig` and `FailureOptions`, constructs the service
from original H/A and mechanism priors, and passes only a syndrome to decode.
It keeps the native success declaration and exact total iteration count, then
checks the returned correction against original H again. Unknown settings and
legacy decoder profiles fail strict configuration validation.
The optional active config tag is `af_bp_config/2`.

`relay_bp` retains its Stage-5 F64 upstream adapter. `beam8` and `bposd`
retain their upstream scientific paths. The timing call still surrounds the
complete decoder service, including AF graph work, Relay legs, output
validation and prediction. Sampling, truth comparison and Parquet writes
remain outside the timer.

## Active data and analysis

New Parquet files have exactly five columns: `shot_id`, `decoder_name`,
`logical_error`, `latency_ns`, and nonnegative exact `total_iterations`.
The schema metadata is `qec_schema=benchmark_results/2`. A declared or
invalid decode writes `logical_error=true` and retains its spent latency and
iteration count. The run directory and Parquet filename conventions are
unchanged. `analysis.simple_results` and `analysis.benchmark_plots` accept
only the new schema. Existing logical-error and mean-time figures keep their
filters and layout; `plot_mean_total_iterations` adds the same filtered
per-family view, including failed shots. Historical multi-schema plot readers
are preserved at `analysis.legacy.benchmark_plots` and do not silently
dispatch from the active reader.

## Bounded examples and evidence

`config/` provides AF-BP smoke, parallel/serial/qDither comparison,
factorization-policy comparison, n_fact comparison, the Stage-5 Relay smoke,
and one-shot BB144 d12/R1 all-decoder examples. All are labeled
non-production. The AF-BP example completed two surface d3 shots in
`assets/runs/2026_09_25_21_51_f4cf7d0a`, producing two
`benchmark_results/2` rows. The BB144 example completed one physical shot
in `assets/runs/2026_09_25_21_52_7f26ed1f`, producing one row each for
AF-BP, Relay, Beam8 and BP-OSD. With deliberately tiny budgets, AF-BP and
Relay declared errors on that shot and retained respectively 1 and 2 spent
iterations. Beam8 and BP-OSD rows reported respectively 2 and 1 iterations.
The BB144 saved file produced a mean total-iteration figure. These runs are
construction/schema checks, not performance or logical-rate estimates.
The two-shot parallel/serial/qDither surface example also completed under
`assets/runs/2026_09_25_21_57_10d32db5`, producing six rows. One bounded
qDither decode declared failure and retained its two spent iterations.

Tests cover exact schema and missing-count rejection, config mapping and
qDither fields, truth-free AF-BP decisions, declared failures with spent work,
identical syndromes across four decoders in a serial paired batch, serial/two
worker non-latency row equality with Relay's stochastic legs disabled, all
four BB144 adapters, synthetic and smoke plotting, and rejection of old
schemas by active readers while the preserved legacy reader still opens one.
Relay with stochastic legs retains upstream worker-local RNG sequencing, so
cross-worker equality is claimed only for the explicitly tested configuration.
Final test counts and build checks are recorded in `STATUS.md`.
