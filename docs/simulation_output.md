# Active minimal simulation output

Each new run has `YYYY_MM_DD_HH_MM_<config-hash-8>/config_resolved.json` and
`data/<code>_d<distance>_r<rounds>_p<rate>_<basis>_results.parquet`. There are
no run manifests, raw samples, copied circuits, file logs or replay facility.
Historical schemas remain readable through legacy consumers.

New runs use Arrow metadata `qec_schema=benchmark_results/3`. Every row has:

| Column | Type | Meaning |
|---|---|---|
| `shot_id` | nonnull string | Stable physical shot identity |
| `decoder_name` | nonnull string | Unique name from resolved config |
| `logical_error` | nonnull bool | Declared/invalid decode or any logical mismatch |
| `latency_ns` | nonnull int64 | Entire decoder service wall time, including failed shots |
| `total_iterations` | nonnull int64 | Completed full BP/Min-Sum steps across the service |
| `converged` | nonnull bool | Syndrome-valid algorithm convergence, independently checked against original H |
| `initial_bp_converged` | nullable bool | AF-BP first graph BP result; null for other decoders and old runs |
| `first_transform_converged` | nullable bool | AF-BP first transformed graph BP result; null if that call did not execute or for other decoders |

For `bposd`, `converged` refers to the BP stage **before OSD**. OSD can
produce a valid correction with `converged=false` and `logical_error=false`.
For Beam8 and Relay-BP it uses the upstream declared convergence/success flag;
for AF-BP it uses the native original-H-valid result. Every true value is also
checked against the original H and syndrome by the adapter. AF-BP stage flags
use the native original-H validation at the initial and first transformed BP
calls; they do not require diagnostics vectors. A successful decode may still
have `logical_error=true` when the logical sector differs from truth.

`P(logical_error | converged)` uses only converged physical shots. The first
transform rescue rate uses successful first transformed BP calls over **all**
shots whose initial AF-BP call failed; a shot without a transform remains in
that denominator. The nullable first-transform field distinguishes that case.
`analysis.simple_results.summarize_run` reports these counts, denominators and
Wilson intervals. Old `benchmark_results/2` files remain readable with
convergence statistics unavailable; they are never inferred or rewritten.

The primary key is `(shot_id, decoder_name)` per condition. A physical shot is
sampled once and passed to all active decoders; its logical truth is compared
only after each decoder returns. `latency_ns` brackets the complete
`DecoderAdapter.decode` call: input conversion, upstream decode, original-H
validation, A prediction and cost. Preparation, warmup, sampling, truth
comparison, row construction and Parquet writes are outside it.
For AF-BP the same boundary includes BP, failure scoring, factorization,
graph transformations and marginal handoff; for Relay it includes all executed
relay legs. Failed services retain spent latency and iterations and are saved
with `logical_error=true`.

For `bposd`, `total_iterations` is upstream BP `.iter` for a nonzero syndrome
and zero for the upstream zero-syndrome shortcut; OSD contributes zero. For
`beam8`, the instrumentation counter sums every initial and masked BP path
actually executed, including paths that did not converge. A zero-syndrome
shortcut contributes zero. Neither value is inferred from budgets or wall time.
For `relay_bp`, `total_iterations` is exactly upstream
`decode_detailed(...).iterations`, including the initial BP run and each
executed relay leg. The adapter calls the single-shot API in each worker.
For `af_bp`, `total_iterations` is the native service's exact sum of completed
BP iterations across its initial and transformed graphs and any qDither chains.

One logical-error trial is one physical shot, with no division by rounds or
number of observables. Failed shots remain in latency and iteration summaries.
The resolved config records the selected OSD order, timing mode, workers,
physical noise and code conditions. `analysis.simple_results.summarize_run`
keeps each run, condition, decoder and execution context separate.
