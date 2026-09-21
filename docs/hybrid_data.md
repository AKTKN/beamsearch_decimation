# Hybrid run data and paired analysis (Stages 4–5)

HSBP-EXP-1.0 is normative. New runs and replays write manifest/marker version 2,
`samples/1`, `decodes/2`, `hybrid_rounds/1`, and `decoder_phases/1`.
Historical v1 schemas and artifacts remain unchanged. `load_run` validates their
original labels before projecting absent hybrid fields and invalid-result logical
mismatch to null in memory. Unsupported versions are rejected.

## Service, ownership and clocks

Workers measure the complete `DecoderAdapter.decode` with Python process_time_ns
and perf_counter_ns. Sampling, setup/warmup, event export, truth labels and writing
are outside that boundary. Lightweight native summaries and counters are inside.
Immediately after the timer stops, the worker copies native rounds/phases before
another decode can replace them. Every enabled baseline runs on the same shot,
including empty-syndrome and search exits. Truth never enters the native service.
The existing spawn scheduler and parent-only output writer are preserved.

Native CLOCK_PROCESS_CPUTIME_ID and CLOCK_MONOTONIC durations, clock resolutions,
Python clock implementations, libc, compiler/build/source identities, execution
order and thread/load metadata are saved. Absolute clock domains are not mixed.
Prefix overlaps search and BP. The six disjoint cost buckets are search,
bp_transition, bp_iterations, prefix_other, osd, and service_other. The two signed
residuals use exact subtraction. Zero tolerance is applied: any negative duration
or residual sets timing_accounting_ok=false. The value is preserved, and paired
cost analysis rejects a flagged observation rather than clamping or dropping it.

Profiling `none` preserves cheap work/exit counters, uses null for unmeasured
phase/prefix/residual durations and accounting flags, and explicitly omits event
shards. Profiling `phases` always declares all four tables, including typed empty
event shards for batches containing only zero-syndrome exits or baselines. No
baseline BP/OSD split is inferred from total time. Baseline hybrid-only fields are
null. The older optional phases_json adapter wall scopes retain their old meaning.

## Identity and atomic publication

All table versions and event omission/presence policy are explicit in run and
batch manifests. Each batch enumerates exact relative shard paths, checksums and
row counts. Each declared table is validated, written, fsynced and exclusively
linked before the atomic batch marker is published. Orphans are ignored for
incomplete runs; missing/corrupted declared shards are errors. Complete runs reject
extra shards. No overwrite/resume is supported. Replays create a new run identity
while preserving physical shot/sampling identity and record their source manifest.

Run instance entries include num_detectors, num_mechanisms and num_observables,
validated against the immutable saved matrices. Physical n remains distinct.
No circuit cache or historical artifact needs rewriting to add these run fields.
Model, noise, decoder, sampling, execution/profiling and run contexts remain
separate throughout analysis. `trial_id` is the new run ID; `physical_trial_id` is
the retained shot ID. Reports count repeated shot/decoder observations and never
pool replay trials into an independent LER confidence interval.

## Labels and validation

V2 valid_logical_mismatch is null for invalid results. Such results have block
failure true, null prediction/cost/correction/mismatch arrays, and all observable
failure bits true. Valid logical mismatch uses the valid-output denominator;
unconditional failure contributions use all physical shots. All 12 BB bits form
one block trial. Empty syndrome has exit_stage=search and reason=zero_syndrome;
its prediction can disagree with truth. OSD entry and successful return differ.

Round keys include run/instance/sampling/batch/shot/decoder plus cycle_index.
Phase keys replace cycle_index with phase_index; OSD has nullable cycle_index.
Indices start at zero. Candidate prediction and mismatch are attached only when
a phase/cycle produced a valid terminal candidate; nonconverged BP has neither.
An exception-interrupted BP cycle can have a null residual_after. Round result
`failed` explicitly represents numerical/resource exceptions. All selected-hint
metadata uses native physical scores and the documented FNV1a64 diagnostic digest.

Validators check exact table membership/nullability, paired completeness, foreign
keys, unique/contiguous event indices, terminal vocabulary, hint nulls, caps/work,
non-overlapping phase intervals, phase/round counters, sums and truth labels.
Counters count actual completed work even on failed shots. Root generation and
zero-syndrome conventions remain those in hybrid_native.md.

## Paired estimates and uncertainty

`analysis.hybrid` exposes stage_statistics, paired_rows, summarize_pair and
paired_statistics. For CPU and wall separately, integer per-shot and aggregate
checks enforce

```
T_H - T_B = P + V - (1-F)*T_B + F*(O-T_B)
```

The exported avoided_baseline term is positive and is subtracted in the identity
and plot. It is split into zero-syndrome, nonzero search, guided BP and pre-OSD
failure. Prefix expenditure on OSD-reached shots is also reported. Fallback
comparison uses actual hybrid OSD cost and actual full baseline service cost.
Failure difference is split by OSD entry and terminal stage. Discordance includes
all four combinations. No reach fraction implies speed or accuracy superiority.

Rate tables use two-sided Wilson intervals and explicit zero/empty denominators.
Paired percentile bootstrap resamples saved shot pairs, or entire batches when
bootstrap_unit=batch. Settings record bootstrap_seed, bootstrap_count, unit and
confidence. It estimates CPU/wall mean differences, all cost terms, LER differences
and ratios of mean times. Ratios are null if baseline mean is zero; valid resample
counts are retained. With accuracy_margin_absolute=null (default), no equivalence
or noninferiority conclusion is produced. A supplied predeclared margin reports
whether the one-sided bootstrap upper bound is strictly below it, with a sample
size caution. No automatic tuning, parameter selection or winner selection occurs.

Reports include failures.json, timings.json, hybrid_stages.json and paired.json,
plus checksummed PNG/PDF LER, ECDF/survivor, stage/reach, disjoint cost, paired-cost
and ablation figures. Stage tables include conditional accuracy, unconditional
failure contributions and per-cycle rescue, expansions/iterations/hints/caps.
Failed shots remain in time distributions. P99.9 is null without the configured
expected tail count; all quantile rows retain sample/tail support flags. A prefix
CPU cap does not bound OSD or the full service time. Optional paired quantile-
difference inference and instrumentation-overhead experiments are not implemented.

The notebook template only calls saved-data APIs and displays report artifacts.
To preserve edited local notebooks, execute the maintained template explicitly:

```bash
scripts/run_benchmark.sh config/hybrid_smoke.yaml.example
scripts/analyze_benchmark.sh config/hybrid_smoke.yaml.example --run SOURCE_RUN
scripts/execute_notebook.sh config/hybrid_smoke.yaml.example --run SOURCE_RUN \
  --notebook notebook/benchmark_analysis.ipynb.example \
  --output assets/notebook/new_hybrid.ipynb
```

These bounded smoke workflows validate software; they do not establish the
scientific hypothesis. Final restoration and acceptance are documented in
[hybrid_acceptance.md](hybrid_acceptance.md).

## Exact Arrow fields

All durations ending in `_ns` are signed int64 nanoseconds. Work counters and
indices are uint64. Boolean vectors use canonical observable order; packed bits
use little bit order. Nullable hybrid columns are required for unrelated decoders
and unmeasured/not-applicable values, not a license to omit measured counters.
Field semantics are defined in HSBP-EXP-1.0 sections 5–6 and above.

### samples/1

| Field | Arrow type | Nullable |
|---|---|---|
| run_id | string | no |
| instance_id | string | no |
| sampling_id | string | no |
| batch_id | uint64 | no |
| shot_index | uint64 | no |
| shot_id | string | no |
| batch_seed | uint64 | no |
| family | string | no |
| distance | int64 | no |
| n | int64 | no |
| k_Z | int64 | no |
| rounds | int64 | no |
| physical_p | double | no |
| noise_id | string | no |
| model_hash | string | no |
| source_hash | string | no |
| config_hash | string | no |
| num_detectors | int64 | no |
| detectors_packed | binary | no |
| actual_observables | list<element: bool not null> | no |

### decodes/2

| Field | Arrow type | Nullable |
|---|---|---|
| run_id | string | no |
| instance_id | string | no |
| sampling_id | string | no |
| batch_id | uint64 | no |
| shot_index | uint64 | no |
| shot_id | string | no |
| batch_seed | uint64 | no |
| family | string | no |
| distance | int64 | no |
| n | int64 | no |
| k_Z | int64 | no |
| rounds | int64 | no |
| physical_p | double | no |
| noise_id | string | no |
| model_hash | string | no |
| source_hash | string | no |
| config_hash | string | no |
| decoder_id | string | no |
| decoder_name | string | no |
| decoder_profile | string | no |
| execution_position | int64 | no |
| prediction | list<element: bool not null> | yes |
| status | string | no |
| native_status | string | no |
| syndrome_valid | bool | no |
| decoding_failure | bool | no |
| valid_logical_mismatch | bool | yes |
| block_failure | bool | no |
| observable_mismatch | list<element: bool not null> | yes |
| observable_total_failure | list<element: bool not null> | no |
| cost | double | yes |
| cpu_ns | int64 | no |
| wall_ns | int64 | no |
| timing_mode | string | no |
| concurrent_load | bool | no |
| workers | int64 | no |
| native_threads | int64 | no |
| blas_threads | int64 | no |
| oversubscribed | bool | no |
| profiling | string | no |
| initial_success | bool | yes |
| initial_iterations | int64 | yes |
| post_iterations | uint64 | yes |
| candidates | uint64 | yes |
| rejected | uint64 | yes |
| retained | uint64 | yes |
| bp_completions | uint64 | yes |
| successful_completions | uint64 | yes |
| selected_pattern | list<element: int64 not null> | yes |
| correction_packed | binary | yes |
| diagnostics_json | string | yes |
| phases_json | string | yes |
| algorithm_version | string | yes |
| exit_stage | string | yes |
| exit_reason | string | yes |
| fallback_reason | string | yes |
| osd_llr_source | string | yes |
| input_syndrome_weight | uint64 | yes |
| cycles_started | uint64 | yes |
| cycles_completed | uint64 | yes |
| search_slices | uint64 | yes |
| search_expanded_nodes | uint64 | yes |
| search_generated_nodes | uint64 | yes |
| search_rejected_local | uint64 | yes |
| search_depth_limited | uint64 | yes |
| search_frontier_peak | uint64 | yes |
| search_guidance_peak | uint64 | yes |
| search_max_depth_reached | uint64 | yes |
| bp_attempts | uint64 | yes |
| bp_iterations | uint64 | yes |
| bp_warm_transitions | uint64 | yes |
| selected_hint_node_id | uint64 | yes |
| selected_hint_ones | uint64 | yes |
| selected_hint_zeros | uint64 | yes |
| hint_disagreements_final | uint64 | yes |
| osd_calls | uint64 | yes |
| effective_osd_order | uint64 | yes |
| osd_entered | bool | yes |
| prefix_cap_hit | bool | yes |
| node_cap_hit | bool | yes |
| timing_accounting_ok | bool | yes |
| native_prefix_cpu_ns | int64 | yes |
| native_prefix_wall_ns | int64 | yes |
| search_cpu_ns | int64 | yes |
| search_wall_ns | int64 | yes |
| bp_transition_cpu_ns | int64 | yes |
| bp_transition_wall_ns | int64 | yes |
| bp_iterations_cpu_ns | int64 | yes |
| bp_iterations_wall_ns | int64 | yes |
| osd_cpu_ns | int64 | yes |
| osd_wall_ns | int64 | yes |
| prefix_other_cpu_ns | int64 | yes |
| prefix_other_wall_ns | int64 | yes |
| service_other_cpu_ns | int64 | yes |
| service_other_wall_ns | int64 | yes |

### hybrid_rounds/1

| Field | Arrow type | Nullable |
|---|---|---|
| run_id | string | no |
| instance_id | string | no |
| sampling_id | string | no |
| decoder_id | string | no |
| shot_id | string | no |
| batch_id | uint64 | no |
| cycle_index | uint64 | no |
| start_cpu_ns | int64 | no |
| end_cpu_ns | int64 | no |
| start_wall_ns | int64 | no |
| end_wall_ns | int64 | no |
| frontier_before | uint64 | no |
| frontier_after | uint64 | no |
| guidance_before | uint64 | no |
| guidance_after | uint64 | no |
| expansion_budget | uint64 | no |
| iteration_budget | uint64 | no |
| expanded | uint64 | no |
| generated | uint64 | no |
| iterations | uint64 | no |
| hint_node_id | uint64 | yes |
| hint_ones | uint64 | yes |
| hint_zeros | uint64 | yes |
| hint_depth | uint64 | yes |
| hint_residual_weight | uint64 | yes |
| residual_before | uint64 | yes |
| residual_after | uint64 | yes |
| hint_g | double | yes |
| hint_h | double | yes |
| hint_f | double | yes |
| hint_digest | string | yes |
| bp_entered | bool | no |
| warm | bool | no |
| node_cap_hit | bool | no |
| prefix_cap_hit | bool | no |
| result | string | no |
| candidate_prediction | list<element: bool not null> | yes |
| candidate_logical_mismatch | bool | yes |

### decoder_phases/1

| Field | Arrow type | Nullable |
|---|---|---|
| run_id | string | no |
| instance_id | string | no |
| sampling_id | string | no |
| decoder_id | string | no |
| shot_id | string | no |
| batch_id | uint64 | no |
| phase_index | uint64 | no |
| phase | string | no |
| cycle_index | uint64 | yes |
| cpu_ns | int64 | no |
| wall_ns | int64 | no |
| native_wall_start_ns | int64 | no |
| native_wall_end_ns | int64 | no |
| work | uint64 | no |
| result | string | no |
| candidate_syndrome_valid | bool | yes |
| candidate_prediction | list<element: bool not null> | yes |
| candidate_logical_mismatch | bool | yes |
