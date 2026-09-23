# LPM-DP-BP-1.0 Stage 4: simulator integration

Stage 4 registers the already-tested native decoder through the existing
truth-free decoder service. It does not change circuit construction, DEM
conversion, noise, sampling, syndrome selection, logical truth generation or
truth comparison. No production sweep was run.

## Identity and strict configuration

The profile is fixed to:

| Field | Value |
|---|---|
| kind | `lpm_dp_bp` |
| profile/name | `lpm_dp_bp_v1` |
| algorithm version | `LPM-DP-BP-1.0` |
| config schema | `lpm_dp_config/1` |

`config.LPMDP` exposes exactly the eight candidate settings and six outer settings
from the note: `history_window`, `history_clip`, `pool_size`,
`local_check_limit`, `max_fixations`, `candidates_per_parent`,
`retained_mass_target`, `proposal_clip`, `initial_iterations`,
`candidate_iterations`, `retained_parents`, `max_cycles`, `scaling_factor` and
`osd_fallback`. Defaults are the reference values. The strict model rejects unknown
or obsolete SEARCH-BP fields, nonfinite/out-of-range values, non-boolean fallback,
and a history window larger than either BP budget.

The runnable bounded template is `config/lpm_dp.yaml.example`. LPM-DP uses
`lpm_dp_results/1`. A run cannot combine LPM-DP and SEARCH-BP because the former's
five-column contract deliberately omits SEARCH-BP's `correction_by_search` field.
LPM-DP can be paired with the existing screened, Beam, BP-OSD and hybrid profiles.

## Native and adapter path

`lpm_dp_bindings.hpp` exposes only settings, the small native result and one
`LPMDPBPDecoder.decode(syndrome)` call. The call releases the GIL. Python maps the
strict configuration once during worker-local construction and passes only the
binary syndrome per shot. Candidate generation, local DP, parent/candidate order,
hard fixation, recursive BP, online retention and optional OSD control all remain
inside `lpm_dp_decoder.hpp`.

`DecoderAdapter.decode` independently checks the returned correction against the
original `H/s`, derives `A*x`, and rejects a non-boolean native `osd_called`. It has
no truth parameter. A native invalid result becomes `DECLARED_FAILURE` with no
correction or prediction; no arbitrary correction is synthesized.

## Result and logical-error contracts

The Arrow metadata is `qec_schema=lpm_dp_results/1` and the exact columns are:

| Field | Type | Meaning |
|---|---|---|
| `shot_id` | nonnull string | existing physical-shot identity |
| `decoder_name` | nonnull string | configured decoder identity label |
| `logical_error` | nonnull bool | declared/invalid decoder failure or logical mismatch |
| `latency_ns` | nonnull int64 | complete decoder-service wall time |
| `osd_called` | nonnull bool | exact native OSD invocation flag |

No correction, truth, candidate, local score, retained mass, cycle count, BP
history or search telemetry is stored. Existing structural shot/name fields remain
for paired simulator bookkeeping. Truth comparison stays in the worker after the
timed decoder service. `failure_labels` counts every declared failure as a logical
error, including bounded exhaustion with `osd_fallback=false`.

`osd_called` is copied directly from the native result. It is false for root/child
BP success and OSD-disabled exhaustion, and true iff the native decoder invoked
OSD once after exhaustion. It is never inferred from status or time.

## Timing boundary

The unchanged worker clocks the complete `DecoderAdapter.decode` call with
`perf_counter_ns`. This includes syndrome copying, initial BP, every LPM-DP and
child-BP operation, retention, optional OSD, original-`H` validation, logical
prediction and cost calculation. Physical sampling, syndrome/truth production,
truth comparison, row normalization and Parquet I/O remain outside the interval.
Failed calls retain their measured latency.

## Simulator-core diff audit

Scientific simulator modules are byte-unchanged: circuit providers, artifact/DEM
construction, noise operations, `runner/plan.py`, seed derivation,
`sample_physical`, truth generation and `failure_labels` semantics were not edited.
The only active runner/storage edits are generic result-contract routing:

- `runner/worker.py` chooses the configured minimal schema and projects the same
  already-computed service result;
- `runner/pipeline.py` passes that schema to the existing parent writer;
- `storage/minimal.py` adds the strict five-column schema and projection;
- `storage/results.py` accepts a schema version when opening/converting rows.

Those lines do not alter physical inputs, decoder scheduling, timers or truth
comparison. The native module, config union and decoder adapter are extension
registration points. `analysis/simple_search_bp.py` only adds read support for the
new saved schema; `analysis/plots.py` adds its label.

## Verification scope

`tests/test_lpm_dp_stage4.py` covers exact defaults/identity, unknown-field
rejection, every configuration value reaching the native settings object, native
construction, truth-free one-call API, real one-shot and repeated-shot decoding,
OSD disabled/enabled exhaustion, exact flags, failure-to-logical-error projection,
the five-column Arrow schema, and a two-shot Surface-d3 run pairing LPM-DP with
unchanged Beam and BP-OSD adapters. These are bounded software smoke checks and
provide no performance or decoder-advantage evidence.

Executed in `search_decimation`: the focused Stage-4 tests passed 4/4; the
deterministic old-decoder regression selection passed 76/76; exact-message and
selected upstream BP tests passed 24/24 with six existing warnings; native Debug
and ASan/UBSan builds each passed 9/9; the dependency/source audit, editable
source-hashed rebuild, strict example validation and pristine-fork restoration
passed. The full project suite reported 335 passed, one skipped and the same
pre-existing legacy SEARCH-BP-v2 template-discovery failure recorded by Stages
1-3. No LPM-DP or existing-decoder regression failed.

There are no algorithmic or numerical deviations from Stage 3. Stage 5 has not
started.
