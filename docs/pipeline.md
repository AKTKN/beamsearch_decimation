# Native decoders and executable paired benchmark (stages 4–5)

Activate `search_decimation` and rebuild the project after any C++/CMake edit:

```bash
conda activate search_decimation
python -m pip install --no-build-isolation -e .
python -m pytest -q
scripts/build_dependencies.sh --check
scripts/run_benchmark.sh config/stage5_validation.yaml
scripts/run_benchmark.sh config/smoke.yaml
scripts/run_benchmark.sh config/latency_smoke.yaml
scripts/replay_samples.sh /path/to/saved/run config/decoder_sweep.yaml
```

Replay accepts any valid configuration YAML. Saved source batches define the physical dataset;
experiment/noise/sampling fields in replay YAML do not regenerate or filter it.
Add -v/--verbose to either run or replay for live preparation and committed-batch
progress, including elapsed run seconds, batch percent and physical-shot totals:

```bash
scripts/run_benchmark.sh config/smoke.yaml --verbose
scripts/replay_samples.sh /path/to/saved/run config/decoder_sweep.yaml -v
scripts/run_benchmark.sh config/smoke.yaml -v > run_path.txt 2> progress.log
```

Progress is flushed to stderr by the parent after each batch is safely committed;
workers do not print per-shot messages. A long batch can therefore produce a quiet
interval. Replay totals come from saved committed batches. stdout still contains only
the successful run path. These presentation messages are outside per-shot decode
timers, and elapsed run time includes preparation and I/O. Verbosity defaults off
and does not alter YAML, sampling, decoder identities or scientific outcomes.

Every invocation creates a new directory under output.root. The four-shot validation
configuration deliberately exercises short final batches on surface d=5,7,9 and BB72.
The ordinary smoke/latency smoke files each request 32 shots per instance at the
explicit implementation example p=0.001. None is a production performance campaign.

Scientific and decoder settings remain exclusively in YAML. Change noise.rates
or noise.sweep (exactly one), and decoders entries for parameter sweeps. Each enabled
configuration needs a unique name and semantic decoder identity. Repeated profiles
with distinct parameter choices are supported; identical semantic configurations
are rejected. The strict schema rejects unsupported settings, including ignored
upstream constructor keywords. Configuration details are in configuration.md.

The project C++ search is static-U exhaustive fixed-q screening with exact (f,rho,
canonical ID) sorting. Every retained candidate uses the fork's same cold-start
flooding sum-product class. Final selection compares unclipped physical cost and
full correction lexicographically. Bounded top K changes memory use only. No early
candidate exit, propagation, warm start, adaptive budget or fallback is implemented.
Reference hard ties use L<0; upstream BP-OSD/beam conventions remain their own.

BP-OSD and beam consume copies of the same immutable canonical H and p. Independent
H validation follows each output and A maps only valid corrections to observables.
BP-OSD convergence describes BP alone; valid OSD outputs remain successes. Exhausted
beam outputs cannot become predictions. Baseline unavailable total search counters
remain null. Empty normalized models have an exact algebraic zero correction only
for zero syndrome. Native allocation/reset behavior and interface ownership are
in the decoders/ and native/ READMEs.

The timing boundary is DecoderAdapter.decode, including all required input/reset,
screening, residual graphs, initial/completion BP, final selection, physical cost,
H validation and A prediction. Worker-local preparation/source checks, circuit
sampling, interprocess communication, truth comparison, serialization and writes
are excluded and recorded separately. Both time.process_time_ns and perf_counter_ns
measure every shot. Baseline objects are never shared across workers or transferred
through queues. Native flooding is an update schedule, not CPU multithreading.

Throughput wall times with multiple workers are labeled concurrent. isolated_latency
uses one worker, with optional CPU affinity. Native/BLAS limits are one, set before
imports and checked against effective pools; oversubscription is explicitly labeled.
Phase profiling is optional, separately labeled, and its nested times must not be
summed. Warmup samples use a separate deterministic stream and remain outside result
rows. Ordinary per-call reset prevents warmup/previous-shot state from entering the
next decode. Clock overhead is reported without subtraction.

Samples and long-form decodes have versioned Arrow schemas in storage/schema.py.
Packed bits use little bit order; all 12 BB observables remain a vector, with one
block-failure indicator per shot. A failed decode has null prediction and cost.
The count summary separates decoding failure, valid mismatch contribution over all
shots, and conditional mismatch over valid outputs. No block-error division by 12
or independence assumption is made. See analysis.md for implemented statistical
summaries, uncertainty intervals, plots and notebook consumers.

Each batch manifest commits both checksummed shards. Parent-only atomic exclusive
publication prevents replacing old results. The run remains incomplete until all
planned counts and decoder identities pass verification. Exceptions retain a
traceback and readable committed pairs; orphan outputs are ignored. Replay can
consume committed subsets, preserving shot IDs and gaps. Resuming an interrupted
run in place is not implemented.

Run directories preserve original/resolved configuration, physical artifacts,
source ZIP with per-file hashes, exact native/source/build identities, dirty Git
patches and untracked relevant source (including worktrees), locks, compiler and
platform/thread metadata, the seed recipe and plan, setup and timer diagnostics.
The replay manifest also preserves source run/configuration identity. Bitwise Stim
resampling is promised only for a fixed pinned environment and batch call layout;
stored samples support exact detector/truth replay without resampling.

Tests include independent scalar BP and full-search oracles; worked-example and
exhaustive lower-bound checks; direct baseline/fresh/reuse/shot-order comparisons;
real serial/spawn/replay parity; short batches and bounded out-of-order execution;
truth-free adapter input; timing boundaries; schema/null/uint64 round trips;
interrupted paired publication and run failure; source ZIP and worktree checks.
Native Debug and ASan/UBSan cover both the reference kernel and project search.
No decoder advantage is inferred from these software validation runs.

Recorded validation:
`config/stage5_validation_serial.yaml` and `config/stage5_validation_latency.yaml`
use the same four-shot batch plan as stage5_validation.yaml. The final default
smoke and isolated runs each have 128 physical samples / 384 decode rows. All
non-timing results matched between worker/mode variants, and replay matched shared
decoder outputs after adding a K=4 configuration. Exact paths and commands are in
`docs/test_results/stage_4_5_summary.json`; replay/run checks can be repeated with
`python docs/test_results/verify_stage_4_5.py`. Earlier development runs remain
preserved and are not the accepted final validation outputs.

Final clean-environment acceptance repeats the full 32-shot physical plan with one,
two and four throughput workers and one isolated worker. Current evidence is in
acceptance_report.md and test_results/stage_6_7_summary.json. Validate integrity and
scientific equality with `python python_scripts/verify_benchmark.py RUN --compare RUN`;
add --allow-additional-decoders when comparing a source run to an expanded replay.
