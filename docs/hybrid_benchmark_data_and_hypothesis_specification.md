# Benchmark and Data Contract for the Search / Soft-BP / OSD-0 Hybrid

**Document ID:** HSBP-EXP-1.0  
**Date:** 2026-09-21  
**Algorithm:** `hybrid_search_soft_bp_osd0_specification.md`, HSBP-ALG-1.0.  
**Status:** Required experiment and migration specification; no performance results are asserted.

## 1. Scientific question

Test whether shallow search and a few stateful soft-guided BP attempts avoid enough baseline decoding work to compensate for their additional cost, while meeting a user-selected accuracy criterion.

There are two independent requirements:

1. The hybrid has lower mean CPU service time, or a useful latency-distribution improvement, relative to its declared baseline.
2. Its logical/block failure rate is sufficiently close to, or better than, that baseline under a declared comparison criterion.

A large search success rate, a large BP convergence rate, or a small OSD reach rate does not establish either requirement on its own. An algorithm that exits quickly with incorrect logical predictions is not a successful result.

Do not select parameters using test-set logical truth and report the resulting minimum as an unbiased benchmark. Keep tuning and evaluation sample sets distinct if tuning is performed. This migration requires working evaluation machinery and smoke runs, not a production parameter search.

## 2. Preserve the physical experiment

| Item | Required behavior |
|---|---|
| Surface code | Rotated surface-code memory, default distances 5, 7, 9; configurable |
| BB code | The existing `[[72,12,6]]` bivariate-bicycle implementation and circuit source |
| Rounds | Default R=d for surface codes; R=6 for the named BB code; explicit resolved values stored |
| Memory | Circuit-level Z-basis memory with the repository's verified selected Z-check detector sector |
| Noise | Preserve the existing circuit-level noise definition and gate schedule; no code-capacity substitution |
| Observables | All selected Z-memory observables; all 12 BB observables, not one chosen logical qubit |
| Sampling | Sample the physical circuit with its configured noise; reuse identical samples across decoders |
| DEM | Preserve undecomposed instruction-level mechanisms, correlations, row projection, and mappings |
| Rates | User-configurable explicit list or sweep; no unrequested production rates or sweep execution |
| Multiprocessing | Existing spawn-based worker design; one mutable decoder instance per worker/model |
| Configuration | All algorithm, experiment, output, seed, timing, and analysis settings in validated YAML |

Z-basis memory and Z-check detectors do not mean “retain only physical Pauli-Z faults.” Preserve the current circuit sampling and detector projection, including the effects of all applicable circuit faults on the measured sector.

At the inspected application revision, the BB circuit uses the qLDPC edge-coloring schedule. It is not documented as the original optimized seven-layer BB schedule. Preserve this choice during the decoder migration, store its exact schedule identity and circuit hash, and do not infer a circuit distance from the code's nominal distance six.

## 3. Decoder comparison matrix

Run each enabled decoder on **every sampled shot**, including shots on which the hybrid exits in search. Preserve paired shot identity through replay.

| Profile | Purpose | Required status |
|---|---|---|
| `hybrid_search_soft_ms_osd0_v1` | Main proposal | Required |
| Explicit upstream BP-min-sum + CS0 profile | Primary current baseline | Required |
| Existing published beam-search profile(s) | Prior requested comparison | Preserve and support |
| Existing BP-min-sum + CS10 profile | Historical accuracy/latency target | Preserve; optional in a new run |
| Search + direct OSD0, BP disabled | Isolate BP's incremental contribution | Provide an ablation config |
| Same hybrid with cold BP at each hint | Isolate within-shot message continuation | Provide an ablation config |
| Direct OSD0 with clipped channel LLRs | Optional control for search + OSD0 | Support if inexpensive; label explicitly |

Do not relabel the old `bposd_ms30_cs10` profile as CS0. Scientific identities must include effective parameters; a display name alone is not sufficient. The main hybrid's OSD order is fixed to zero even if optional historical baselines use other orders.

The isolated-latency run uses one worker, one native thread, and one BLAS/OpenMP thread. The throughput run may use multiple workers and must record concurrent load. Do not pool those timing regimes. Use the existing deterministic cyclic decoder-order policy, keyed by shot identity, to avoid always timing one decoder first. Record execution position.

## 4. Timing boundaries

### 4.1 Outer service time

Preserve the existing per-shot `cpu_ns` and `wall_ns` definition: input preparation and validation inside the decoder adapter, the native decoder call, full correction validation, and observable prediction are included. Circuit sampling, worker setup, compilation, first-time model preparation, truth-based labeling, Parquet serialization, and analysis are excluded.

The outer CPU clock remains Python `process_time_ns()`. Native phase CPU timing must use a compatible monotone process-CPU clock, normally `clock_gettime(CLOCK_PROCESS_CPUTIME_ID)` on the supported Linux platform. Record the clock implementation and measured resolution. Use `perf_counter_ns()` externally and a documented monotone wall clock internally. Never compare absolute timestamps from different clock domains; compare durations.

One native thread per decoder is required for the primary timing comparison. Process CPU time with multiple native threads measures summed CPU consumption and is not a direct latency measurement; such runs need distinct timing identities.

### 4.2 Native prefix and disjoint phase calls

Time these native calls with both CPU and wall durations:

- `search`: one bounded search slice, including its heap work, child construction, heuristic evaluation, and its internal validity checks;
- `bp_transition`: field replacement and initialization/warm continuation, including its validity test;
- `bp_iterations`: one block of up to the configured number of full iterations, including their validity tests;
- `osd`: the OSD-only bridge, including per-shot ordering and elimination.

These phase-call intervals do not overlap. Record aggregate `native_prefix_cpu_ns` and `native_prefix_wall_ns` from native decode entry until either the decision to return early or the handoff into OSD. This includes reset/root work and prefix control overhead. Prefix time overlaps its constituent search/BP phases by definition; never add the prefix to those phases in a total.

Define, separately for CPU and wall time,

\[
P_j=\text{native prefix duration},\qquad
O_j=\text{OSD phase duration, or zero if not entered},
\]

\[
V_j=T_{H,j}-P_j-O_j.
\]

Here \(T_H\) is outer hybrid service time and \(V\) contains adapter work, final validation, result assembly, clock/call overhead not included in the prefix, and other residual service work. Save the residual, not just phase sums. Unexpected negative residuals are an accounting error; do not silently clamp them to zero. Permit only a documented clock-resolution tolerance and flag any accepted discrepancy.

Also save `prefix_other_* = native_prefix_* - search_* - bp_transition_* - bp_iterations_*`. This makes reset and control overhead visible without timing each child individually.

### 4.3 Avoid changing the measured algorithm through logging

Use preallocated native records and counters. One phase record per call and one summary per outer cycle is sufficient; a record per search node or BP iteration is not mandatory. Do not invoke Python callbacks, JSON formatting, filesystem I/O, or Parquet writers inside native search/BP loops.

Keep large trace conversion and all truth-dependent labels outside the service timer. A practical adapter contract returns a correction and lightweight summaries during decode, then exports optional compact native event buffers before decoding the next shot, outside the timed interval. Buffer ownership and lifetime must be explicit. If some conversion remains inside service time, document and measure it consistently rather than subtracting an estimated cost.

Support `profiling=none` for timing-overhead controls and `profiling=phases` for the hypothesis experiment. `phases` is required for the full cost decomposition. Null phase durations in `none` mean unmeasured, not zero. Report instrumentation-overhead measurements separately; do not subtract them from individual shot times.

## 5. Terminal-stage semantics and error labels

For the hybrid, `exit_stage` is exactly one of `search`, `guided_bp`, `osd`, or `failed`. `osd_entered` is a separate Boolean. Therefore an invalid OSD result has `exit_stage=failed` and `osd_entered=true`.

Useful `exit_reason` values include `zero_syndrome`, `search_goal_generated`, `bp_transition_valid`, `bp_iteration_valid`, `osd_valid`, `inconsistent_syndrome`, `osd_invalid`, `numerical_failure`, and `resource_failure`. Define an enumerated vocabulary in code and docs. `fallback_reason` is nullable if OSD was not reached; otherwise it records `cycle_budget`, `frontier_and_hints_exhausted`, `node_cap`, or `prefix_cpu_cap`. Invalid model/input errors must not be disguised as ordinary budget exhaustion.

Retain the existing labels:

\[
D_j=\mathbf1\{\text{no valid correction returned}\},
\]

\[
Q_j=\mathbf1\{\text{valid correction and }\hat\ell_j\ne\ell_{\mathrm{true},j}\},
\qquad E_j=D_j\lor Q_j.
\]

`decoding_failure=D`, `valid_logical_mismatch` is nullable on invalid results under the existing convention, and `block_failure=E` is the primary total-failure measure. Retain observable-level mismatch/failure arrays as well.

The block failure rate is per physical memory shot. Do not divide it by distance, rounds, or 12 BB logical qubits. An optional per-observable average or fitted per-round quantity must be labeled as a different statistic with its assumptions.

A nonconverged BP hard decision has no valid logical-correction error label. A phase record may store its residual weight, but its logical mismatch is null. Only a phase that actually produced a valid correction can have a meaningful candidate logical label. When the decoder stops at first validity, that is also the terminal result's label.

## 6. Parquet schema migration

### 6.1 Versioning and file layout

Retain the existing samples schema and physical sampling identity. Introduce `decodes/2`, `hybrid_rounds/1`, and `decoder_phases/1`, together with run-manifest and batch-marker version 2. Table versions are independent of the run-manifest version.

Keep readers for historical version-1 runs and their exact schemas. For combined analysis, project new fields as nullable in memory; do not rewrite old Parquet or fabricate old phase data. Reject unsupported future versions explicitly.

Use the existing timestamped run-folder convention and committed-batch layout. Extend each new batch's atomic marker to enumerate every expected shard, schema version, row count, and checksum. Under phase profiling, this includes samples, decodes, hybrid-round summaries, and phase events; write schema-correct empty tables when there are no corresponding events. Under `profiling=none`, declare omitted event tables explicitly in the manifest and marker policy.

The parent process remains the sole writer. Worker results must carry new native summaries/events through the pipeline to the writer. Commit only after all paired decoder results and all declared shards are durable. A crash before the marker leaves an uncommitted batch that readers ignore. A marker referencing missing or corrupted data is an integrity error, not a partial run to silently accept.

### 6.2 Existing identifiers to retain

Retain all current common fields, including `run_id`, `instance_id`, `sampling_id`, `batch_id`, `shot_index`, `shot_id`, `batch_seed`, code family and distance, physical code length, `k_Z`, rounds, physical error rate, noise identity, and model/source/config hashes. Retain decoder identity, execution position, timing environment, correction/prediction fields, and existing failure labels.

Also retain canonical DEM sizes separately as `num_detectors`, `num_mechanisms`, and `num_observables` in instance metadata. Do not overwrite the existing code-length field with a mechanism count.

### 6.3 New `decodes/2` columns

The implementation must specify exact Arrow types and nullability in `storage/schema.py`. Use signed 64-bit nanoseconds for durations/residuals, unsigned 64-bit work counters, Boolean flags, and UTF-8 strings or documented enum encodings. The table below defines semantics. All hybrid-only columns are null for unrelated decoders unless a value is actually measured under the same definition.

| Column/group | Meaning |
|---|---|
| `algorithm_version` | Normative algorithm version and profile identity |
| `exit_stage`, `exit_reason` | Terminal stage and precise reason |
| `fallback_reason` | Why the hybrid invoked OSD; null otherwise |
| `input_syndrome_weight` | Initial selected-detector popcount |
| `cycles_started`, `cycles_completed` | Started cycles; fully completed nonterminal cycles |
| `search_slices`, `search_expanded_nodes` | Search calls and popped expandable nodes |
| `search_generated_nodes` | Constructed nodes including the root when created |
| `search_rejected_local`, `search_depth_limited` | Locally inconsistent children; nonterminal depth-D nodes |
| `search_frontier_peak`, `search_guidance_peak` | Peak counts of expansion nodes and unused guidance patterns |
| `search_max_depth_reached` | Largest constructed depth |
| `bp_attempts`, `bp_iterations` | Hints used and completed flooding iterations |
| `bp_warm_transitions` | Attempts continuing an existing within-shot message state |
| `selected_hint_node_id` | Last used hint or null if none |
| `selected_hint_ones`, `selected_hint_zeros` | Last hint's assignment counts or null |
| `hint_disagreements_final` | Final valid correction's disagreements with last hint; null without both |
| `osd_entered`, `osd_calls`, `effective_osd_order` | Reach flag, zero/one call count, and zero when invoked |
| `osd_llr_source` | `last_guided_bp` or `clipped_channel`; null if not invoked |
| `prefix_cap_hit`, `node_cap_hit` | Explicit prefix-limit flags |
| `search_cpu_ns`, `search_wall_ns` | Sums of search phase calls |
| `bp_transition_cpu_ns`, `bp_transition_wall_ns` | Sums of initialization/hint-transition calls |
| `bp_iterations_cpu_ns`, `bp_iterations_wall_ns` | Sums of BP iteration-block calls |
| `osd_cpu_ns`, `osd_wall_ns` | OSD-only call duration; zero if measured and not called |
| `native_prefix_cpu_ns`, `native_prefix_wall_ns` | Prefix aggregate defined in Section 4 |
| `prefix_other_cpu_ns`, `prefix_other_wall_ns` | Prefix minus its measured constituent phases |
| `service_other_cpu_ns`, `service_other_wall_ns` | Outer service minus prefix and OSD |
| `timing_accounting_ok` | Clock consistency check; null when not measurable |
| Existing `cpu_ns`, `wall_ns` | Full outer service time; keep the established meaning |

Counters should be present even in `profiling=none` if their overhead is negligible. Counts distinguish a phase that was not entered from a phase that was entered but completed zero iterations. Increment `cycles_completed` after the cycle's search and optional BP work finish without an early valid return or hard-cap interruption, before checking ordinary pool/cycle exhaustion; thus it can include the final cycle before ordinary fallback. Empty-syndrome exits have no BP attempts or OSD calls. The implementation must document whether the root was materialized before returning zero; the reference returns first, so `search_generated_nodes=0` for that path.

### 6.4 `hybrid_rounds/1`

One row per started hybrid cycle under phase profiling. Key by `(run_id, instance_id, decoder_id, shot_id, cycle_index)` and retain `sampling_id` and `batch_id`. Use zero-based stored `cycle_index`; equations use one-based cycle numbers.

Required contents:

- cycle start/end cumulative CPU and wall durations relative to native entry;
- frontier and unused-guidance sizes before/after the cycle;
- configured expansion and iteration budgets, actual work counts, and cap flags;
- selected hint `node_id`, pattern digest, depth, numbers of ones/zeros, and `(g,h,f,residual_weight)`;
- whether BP was entered, whether it was warm, completed iterations, residual weight before and after the attempt;
- cycle result (`continue`, `search_exit`, `bp_exit`, `fallback`) and nullable terminal prediction/logical labels.

A cycle ending during search has no selected hint or BP records. Unselected-hint fields are null, not zero. Heavy lists of assigned indices are optional trace payloads; counts and a canonical digest are mandatory when a hint is selected.

### 6.5 `decoder_phases/1`

One row per actual timed phase call. Key by shot/decoder identifiers plus a monotone `phase_index`. Store `phase`, nullable `cycle_index` (OSD has none), CPU/wall durations, relative native wall start/end, phase result, applicable work counters, nullable returned-candidate syndrome validity, and nullable candidate observable prediction and logical mismatch.

Do not add synthetic zero-duration event rows for calls that did not happen. Summaries may contain zero for a measured-but-unentered phase. Baseline event rows are optional unless the baseline genuinely exposes matching instrumentation; never infer baseline BP/OSD CPU splits from total time.

The evaluator computes logical labels after timing. Native code returns no truth-dependent fields. Foreign-key, phase-order, duration-sum, and final-label consistency checks are required.

## 7. Exact paired evaluation of the runtime hypothesis

For each common shot \(j\), let \(T_{B,j}\) be the observed baseline CPU service time and \(T_{H,j}\) the hybrid CPU service time. Define

\[
F_j=\mathbf1\{\text{hybrid entered OSD}\},\qquad A_j=1-F_j.
\]

`A` here means “did not enter OSD,” which includes explicit pre-OSD failure if one occurs. Report such failures separately. To interpret it as successful early exit, verify there are no such failures or replace it by separate search/BP/failure indicators.

With \(O_j=0\) when OSD is not entered and \(T_{H,j}=P_j+O_j+V_j\), the exact sample identity is

\[
T_{H,j}-T_{B,j}
=P_j+V_j-A_jT_{B,j}+F_j(O_j-T_{B,j}).
\]

Consequently,

\[
\overline{T_H-T_B}
=\overline P+\overline V
-\overline{A T_B}
+\overline{F(O-T_B)}.
\]

Report each term, its sample size, and a paired confidence interval where applicable:

| Term | Interpretation |
|---|---|
| \(\overline P\) | Native preprocessing expenditure across all shots |
| \(\overline V\) | Remaining hybrid service expenditure |
| \(\overline{A T_B}\) | Observed baseline service cost avoided on shots that skipped OSD |
| \(\overline{F(O-T_B)}\) | Difference between hybrid OSD-only fallback and complete baseline service on reached shots |

The hybrid is faster in mean CPU time exactly when the right side is negative. Compute the identity both per shot and after aggregation; use it as a data-accounting test as well as a scientific diagnostic.

Do not replace \(\overline{A T_B}\) by \(\Pr(A)\,\overline{T_B}\). Easy and hard shots can have different baseline costs. Do not assume \(O=T_B\): the hybrid runs OSD directly on guided beliefs, whereas baseline BP-OSD runs its own BP and may exit before OSD.

Split the avoided-baseline term by `zero_syndrome`, nonzero `search`, and `guided_bp` exits. This reveals whether a large early-exit fraction is mostly an already-cheap zero-syndrome shortcut. Also report prefix costs on shots that eventually reached OSD, since those shots carry the unsuccessful preprocessing burden.

These are paired empirical accounting terms, not a claim that running the baseline alongside the hybrid has zero cache or order effects. Retain the timing-order controls and confirm key latency findings in isolated runs.

## 8. Accuracy accounting and rates

Let \(E_H,E_B\) be the total block-failure indicators, including invalid decoding. Then

\[
\overline{E_H-E_B}
=\overline{A(E_H-E_B)}+\overline{F(E_H-E_B)}.
\]

Further split by terminal stage. Report the paired discordance counts: hybrid fails/baseline succeeds, hybrid succeeds/baseline fails, both fail, and both succeed. These identify whether early termination introduces errors that fallback would otherwise have avoided.

For \(N\) hybrid shots, report:

- search exit fraction, with zero-syndrome and nonzero-syndrome components;
- guided-BP exit fraction;
- OSD reach fraction, OSD valid-return fraction, and total invalid-return fraction;
- conditional logical mismatch among valid exits at each stage;
- each stage's unconditional contribution to total block failure;
- total block failure rate and observable-level statistics.

All-shot exit fractions use \(N\) as the denominator. “BP rescue rate” additionally reports valid BP exits divided by shots that entered BP. “OSD success rate” uses shots that entered OSD. Show denominators and counts explicitly; undefined rates with zero denominator are null.

Searching or BP can visit multiple cycles, so the fraction entering search plus the fraction entering BP plus OSD reach need not sum to one. Terminal-stage fractions, including explicit failures, must sum to one.

Use Wilson intervals for individual Bernoulli rates and a paired analysis for differences. Bootstrap paired shots for mean CPU differences, failure differences, cost-decomposition terms, and mean-time ratios. Quantile differences must bootstrap the paired sample, not average per-shot quantile surrogates. Record bootstrap seed and count. If timing shows batch dependence, provide a batch-block bootstrap option and label the resampling unit.

Repeated replays of the same physical shots do not create independent logical-error samples. Group repeated timing trials explicitly and avoid duplicate truth observations in LER confidence intervals. Report zero observed failures with an uncertainty bound, not as proof of zero LER.

## 9. Analysis outputs

Provide reusable functions and a notebook that generate:

1. Block failure rate versus physical error rate for every enabled decoder, with intervals and shot counts.
2. Mean, median, p90, p95, p99, and, only with adequate tail counts, p99.9 CPU and wall service times. Include failed shots; report tail counts and timing regime.
3. CPU/wall empirical CDFs and survivor curves, both overall and conditioned on terminal stage.
4. Search/BP/OSD terminal fractions and OSD reach versus physical error rate.
5. Native phase costs and the four-term paired mean-cost decomposition in Section 7.
6. Stage-conditioned logical mismatch, unconditional stage failure contributions, and paired discordance tables.
7. Cycle-level rescue counts, expansions, BP iterations, hint sizes, and cap-hit frequencies.
8. Accuracy versus mean/p99 CPU comparisons across explicitly configured ablations, without automatically declaring a winner from noisy point estimates.

For a configured deadline \(\tau\), an optional completion-deadline failure statistic is

\[
\Pr(T>\tau)+\Pr(T\leq\tau, E=1).
\]

It counts late or incorrect final outputs. It is not the accuracy of an unimplemented anytime decoder that could emit an earlier incumbent.

Support a nullable user-specified `accuracy_margin_absolute` and confidence level for noninferiority reporting. If absent, report estimates and intervals without declaring accuracy equivalence. A formal conclusion requires its predeclared criterion; a nonsignificant difference is not evidence of equality.

## 10. Reproducibility manifest

Save a resolved JSON manifest containing the full expanded YAML, all seeds, sampling identities, decoder identities, algorithm/document versions, per-instance model sizes, exact code/circuit/noise/sector settings, dependency pins and patch digests, source and native-build hashes, compiler and optimization flags, Python/package versions, CPU/OS/libc details, clock definitions, worker/thread/affinity configuration, timing order, instrumentation mode, table versions, and expected output policy.

Keep the existing exact circuit/DEM/model artifacts and logical-observable maps. Store graph and code length separately. Record whether CPU time limits are active: replay with clock-based stopping can change decoder paths across machines or loads even when seeds match.

A replay must validate source sample/model compatibility before decoding. Its new decoder run receives a new timestamped output directory and new run identity while retaining physical sample identity. Do not overwrite or resume into old shards. Never include sampled truth in a decoder-specific seed or selection policy.

## 11. Migration touchpoints in the inspected repository

| Existing area | Required extension |
|---|---|
| `src/qec_bp_benchmark/config.py` | New discriminated decoder kind, strict resolved budgets, CS0 profile, ablation/timing/output settings |
| `src/qec_bp_benchmark/bp.py` | Verified opt-in stateful fork interface; retain the old cold BP API |
| `src/qec_bp_benchmark/native/` | New search/hybrid kernel, OSD-only bridge integration, compact phase/cycle records |
| `src/qec_bp_benchmark/decoders/__init__.py` | Explicit dispatch and identity for every kind, mutable-session lifecycle, result summaries |
| `src/qec_bp_benchmark/runner/worker.py` | Paired execution, native event extraction outside timing, truth-based event labels |
| `src/qec_bp_benchmark/runner/pipeline.py` | Carry added tables to the parent writer |
| `src/qec_bp_benchmark/storage/` | Versioned exact schemas, atomic multi-table batches, v1 readers |
| `src/qec_bp_benchmark/identity.py` and `provenance/` | Version/config/source identity expansion and all new authored native sources |
| `analysis/io.py` | Version dispatch, new event tables, v1 nullable projection, compatibility checks |
| `analysis/statistics.py` and new focused analysis module | Paired hypotheses, stage rates, bootstrap, accounting tests |
| `analysis/report.py`, notebooks and script/config templates | Reproducible plots and summaries from saved data |
| `external_lib/`, build/audit scripts, CMake | Reconstructible fork patch, native tests, all authored-file hashes |
| `AGENTS.md`, `STATUS.md`, module READMEs, `docs/` | New contract, preserved legacy profile, current tested status |

The current storage layer expects exact schemas and paired sample/decoder shards, and the reader rejects unknown manifest versions. Adding keys to an in-memory result dictionary alone will not complete this migration.

## 12. Acceptance tests for the experiment

- Synthetic paired rows reproduce the runtime and accuracy identities exactly, including early failures, baseline BP exits, and fallback outcomes that differ from baseline.
- Stage denominators, null logical labels, zero-duration versus unmeasured phases, and empty-syndrome counts are correct.
- Phase/cycle totals agree with decode summaries and valid terminal labels; truth is never passed into native decoding.
- Every actual stage is covered by deterministic tiny fixtures; do not require rare paths to appear by chance in a smoke run.
- Version-1 fixtures remain readable; version-2 runs round-trip with strict schemas and exact pairing.
- Missing/corrupted shards, duplicated rows, unknown versions, incompatible model identities, and interrupted batch writes are rejected or ignored according to the commit protocol.
- One-worker versus multi-worker runs with deterministic work budgets have identical scientific outputs and counters for the same shots; timing fields are intentionally different.
- Replay preserves samples and produces a new run; repeated timing trials are not double-counted as independent LER shots.
- Small surface-code and BB end-to-end smoke runs, including all 12 BB observables, complete and produce valid reports. Run a one-worker latency smoke separately.
- Configured analysis can be rerun from Parquet and manifest artifacts alone. Notebook execution is tested on smoke data.

Do not claim the scientific hypothesis is confirmed by passing software tests or by a small smoke run. The deliverable is an implementation that can measure and potentially falsify the hypothesis.
