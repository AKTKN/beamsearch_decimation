# Exposed-setting audit

| Group | Executed consumer / persisted evidence | Checks |
|---|---|---|
| experiment family/distance/rounds/basis/sector | circuits providers + instance/observable/detector maps; round override retained | test_circuits, BB GF(2) basis, noiseless and physical fixtures |
| physical rates / linear or log grid | expanded_rates and scientific task/artifact identities | test_config; empty production grid rejected before run creation |
| five noise multipliers and idle | common injection and saved inventory/eligible-qubit set | circuit operation/fault tests |
| circuit provider/schedule/boundaries/cache | pinned provider, exact Stim bytes, content-addressed cache | repeated artifacts and hashes |
| undecomposed DEM / explicit disjoint option / no gauges or merging | extraction options/hash and canonical H/A/p | separator, hyperedge, repeat-offset, logical-only and zero tests |
| screened T0/Tpost/history/M/q/K/Lmax | native Settings and embedded kernel/search identities | full scalar/search oracles, top K, structural fixed bits, no extensions |
| BP-OSD max_iter/order and fixed MS/parallel/scale/CS/thread | actual fork API; result H validation | direct API and 288 pristine comparisons |
| beam max_rounds/width/results/initial_iters/iters_per_round | separate published matrix API, fixed upstream properties | constructor properties, direct output and shot-reuse tests |
| shot/batch counts, seeds, warmup, raw samples | immutable task plan, uint64 seed recipe, per-batch sampling/warmup metadata | same-shot, order/worker/replay equality, short batches |
| workers/spawn/max_pending/cache/native+BLAS threads/affinity | bounded scheduler, worker-local LRU, environment + per-worker thread checks | bounds/errors/cache/worker equality; affinity subset validation |
| CPU/wall mode/order/profiling | whole adapter service, cyclic stable-ID order, nested optional phases | instrumented timing boundary, failure timing, isolated smoke |
| output root/compression/shard/trace/correction flags | exclusive run, strict Arrow, paired commits, optional native traces/canonical correction bytes | round trips, nulls, second-shard interruption and duplicates |
| analysis confidence/quantiles/plots/input/output/tail threshold/strata | report manifest, count/quantile JSON, standalone plots and notebook | known Wilson endpoints, exact quantiles, zero limits, protected groups |

All accepted choices are visible in resolved configuration and manifests. Unknown
settings are rejected. Phase profiling stays labeled separately; unavailable baseline
counters remain null. Analysis never changes physical inputs or invokes decoders. The
specified reference algorithm and ordinary/published baselines remain scientifically
unchanged. Saved scientific artifacts are verified before use and copied into runs.


## Hybrid Stage 1 audit

| New setting | Consumer/evidence now | Deferred executable consumer |
|---|---|---|
| hybrid kind/profile/version | strict discrimination, availability guard, complete decoder identity | native hybrid Stage 3 |
| search depth/cycles/expansion/node/CPU budgets and policy literals | validated finite limits and resolved immutable budget lists; test_hybrid_config | persistent search and caps Stage 3 |
| BP method/schedule/scale/clip/iterations/hints/warm flag | nested strict model, ablation consistency and full identity; test_hybrid_config | fork session Stage 2, native hints Stage 3 |
| OSD-only/order/source/ordering and numerics | fixed supported literals, nonzero order rejected | direct bridge Stage 2 and integration Stage 3 |
| timing.profiling | unchanged run/config identity and legacy timing | hybrid disjoint CPU/wall records Stage 3, v2 storage Stage 4 |
| bposd_ms30_cs0 | existing actual upstream adapter, direct native/reuse/empty-shape comparisons | none |

Availability checks prevent deferred settings from being silently ignored by any
running decoder. Existing scientific/configuration/sampling boundaries remain.

## Hybrid Stages 2-3 consumers

All hybrid search/BP/fallback/numerical fields now map to checked native Settings
and the compiled kernel. Tests compare scalar/list identity, actual warm/cold/no-BP
behavior, finite caps and invalid inputs. Profiling enables process CPU/monotone
wall native events and null unmeasured times; summaries remain available in none.
Per-node diagnostics are rejected explicitly. Only runner/storage support remains
guarded for Stage 4. See hybrid_native.md for the native method/setting mapping.

## Hybrid Stages 4–5 consumers

The Stage 4 guard is removed: worker telemetry reaches strict v2 storage, manifests
and version-dispatched analysis. Profiling none/phases controls explicit event
omission/typed empty shards and null/measured times. Model dimensions, clock/libc
metadata and active CPU caps are saved independently of physical code length.
Analysis bootstrap_seed/count/unit and accuracy_margin_absolute are consumed by
analysis.hybrid; confidence controls Wilson and paired bootstrap intervals. Reports
record all settings, repetition policy, denominators and output hashes. Focused
hand-counted tests cover misleading speed/reach cases, replay independence, batch
resampling, nulls, exact cost/error identities and corrupted event data.
