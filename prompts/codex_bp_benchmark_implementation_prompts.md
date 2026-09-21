# Staged Codex Prompts for a Circuit-Level BP Decoder Benchmark

Version 1.0 — 20 September 2026
First, create new anaconda environment as 'search_decimation', and use this environment for running programs.

## How to use this document

Place this document, `bp_decimation_screening_specification.md`, and the six supplied Python reference modules in the implementation workspace. The reference modules are `config.py`, `pairing.py`, `parallel_runner.py`, `provenance.py`, `sampling.py`, and `storage.py`. They are examples from another project, not an existing implementation of this benchmark.

Send Prompts 1–7 below to Codex in order. Each fenced prompt is a complete stage instruction. The project contract in Sections A–J applies to every stage and should be available as a file throughout implementation. Finish and test one stage before sending the next prompt. A stage should produce working code and recorded test results, not only a design proposal.

The earlier decoder specification defines the proposed algorithm. This document defines its implementation environment and benchmark. Production physical-error-rate values will be supplied by the user later; a small explicitly labeled smoke configuration is sufficient for implementation validation.

## A. Project contract: objectives and scope

Build a maintainable Python/C++ research package, tentatively named `qec_bp_benchmark`, to compare:

1. The screened-decimation BP decoder specified in `bp_decimation_screening_specification.md`.
2. BP-OSD from the `ldpc` library.
3. The published IonQ BeamSearchDecoder implementation.

The initial scientific outputs are logical memory failure rates and distributions of single-shot decoding times on CPUs. Preserve per-shot data so that subsequent analyses can be designed without rerunning the entire simulation.

Required code families:

| Family | Default parameters | Memory duration | Observables |
|---|---|---|---|
| Rotated surface code | \(d=5,7,9\), configurable | \(R=d\) syndrome-extraction rounds | One logical \(Z\) |
| Bivariate bicycle code | \([[72,12,6]]\) | \(R=6=d\) syndrome-extraction rounds | All 12 independent logical \(Z\) observables |

Allow an explicit round-count override, but record the resolved count and distinguish such runs from the default \(R=d\) experiment.

Interpret “Z-basis, one Pauli sector” as a Z-memory experiment: prepare the appropriate logical Z state, track logical Z measurement flips, and decode using Z-check detector information. This detects the X component of physical Pauli faults, including the X component of Y faults. It does not mean pure-Z physical noise. The physical circuit still executes both X- and Z-stabilizer extraction operations. Do not remove the other sector's physical gates merely because its detector outcomes are excluded from the decoder input.

Use full circuit-level Pauli noise and sample the physical Stim circuit. Code-capacity sampling, phenomenological noise, and DEM-only sampling are not substitutes for the requested benchmark. DEM sampling is permitted only in labeled converter tests.

The default experiment is offline decoding of the complete \(R\)-round record. It does not implement a sliding window or a streaming decoder.

Implement the reference screened-decimation algorithm first. Do not introduce adaptive candidate pools, beam pruning, best-first search, degree-one propagation during screening, warm starts, damping, learned scores, or additional decoder fallbacks into its default profile. These are separate algorithms or extensions, not implementation optimizations.

### Scientific outcomes

For shot \(t\), let \(y_t\in\mathbb F_2^{k_Z}\) be the sampled observable-flip vector. If a decoder returns a valid correction \(\hat e_t\), its prediction is \(\hat y_t=A\hat e_t\), including any exact preprocessing offsets.

Let \(a_t=1\) denote a declared decoding failure, exhausted search without a valid correction, or returned correction that fails the input syndrome. Define

\[
F_t=
\begin{cases}
1,&a_t=1,\\
\mathbf 1[\hat y_t\ne y_t],&a_t=0.
\end{cases}
\]

The primary failure rate is \(N^{-1}\sum_t F_t\), labeled “Z-memory block failure rate, including decoding failures.” Also report:

- decoding-failure rate \(N^{-1}\sum_t a_t\);
- valid-output logical-mismatch contribution \(N^{-1}\sum_t(1-a_t)\mathbf 1[\hat y_t\ne y_t]\);
- valid-output conditional logical-mismatch rate, with its smaller denominator stated;
- per-observable mismatch information and, separately, per-observable total failure rates if failures are counted against each observable.

For BB72, a block fails when any of its 12 tracked logical observables fails. Do not estimate per-logical-qubit error by dividing the block failure rate by 12. Do not multiply a one-sector result by two to present a full quantum-memory failure rate. Do not interpret block latency divided by \(R\) as an independently measured online round latency.

An unexpected programming exception is a failed experiment task, not an ordinary decoder failure. Preserve its traceback, mark the run incomplete, and propagate the exception.

## B. Required repository structure and engineering rules

Use exactly these requested top-level directory names:

| Directory | Responsibility |
|---|---|
| `src/` | Importable simulation package, decoder adapters, and project-owned C++ implementation |
| `python_scripts/` | Thin Python execution, validation, and analysis entry points |
| `scripts/` | Shell launchers that call Python entry points with YAML configurations |
| `config/` | Validated YAML configurations and examples |
| `analysis/` | Importable data-loading, statistical-summary, and plotting modules |
| `notebook/` | Notebooks using the analysis modules |
| `external_lib/` | Pinned external source checkouts, fork branches, and dependency manifest |
| `assets/` | Timestamped experiment outputs |
| `tests/` | Python, C++, integration, and external-modification regression tests |

Also create `docs/` and `simulation_data/`. The latter holds generated circuits, DEMs, matrices, detector maps, observable maps, and reusable fixtures or caches. Separate immutable scientific artifacts from mutable output tables.

At the repository root, create `AGENTS.md`, `STATUS.md`, `README.md`, `pyproject.toml`, an appropriate dependency lock, and the required native build configuration.

- `AGENTS.md`: project overview, directory responsibilities, scientific invariants, build/test commands, documentation obligations, and conventions for future changes. Preserve applicable pre-existing instructions.
- `STATUS.md`: implemented features, actual test commands and outcomes, current limitations, external-source identities, and the next unfinished stage. Never mark a stage complete merely because files exist.
- Each first-party module directory: a concise `README.md` explaining responsibilities, public APIs, data flow, assumptions, and relevant tests. This includes C++ module directories. For external packages, retain their original documentation and add integration notes under `external_lib/`.

Use English for all code comments, docstrings, configuration comments, documentation, notebooks, and runtime messages.

Use typed Python interfaces, explicit result types, small functions, and a limited number of clear module boundaries. Public functions must document arguments, units, array shapes, return values, exceptions, ownership, and mutation where relevant. C++ interfaces must document buffer lifetime and thread-safety constraints. Comments should explain invariants or non-obvious choices, not repeat statements.

Prefer C++17 or later, RAII, checked shapes at language boundaries, deterministic ordering, and contiguous or sparse storage appropriate to the operation. Keep parsing, plotting, and orchestration out of native decoding hot paths. Do not write a general workflow framework, plugin marketplace, or distributed scheduler for this initial package.

Build and test each smallest meaningful component when it is introduced. Compilation, imports, and native/Python boundary tests are required before integrating that component. Do not defer all tests until the final stage.

All experiment and decoder settings must be configurable through validated YAML. Do not hide tunable values in notebooks, shell scripts, environment variables, or module-level experiment constants. Mathematical definitions of a named algorithm profile may be fixed; unsupported overrides must be rejected rather than ignored. Record fixed upstream implementation conventions in the resolved metadata.

## C. External software and source audit

Use these primary sources as starting points. Resolve compatible revisions during implementation and pin exact commit hashes; a moving branch name is insufficient.

| Purpose | Source and verified integration point |
|---|---|
| BP and BP-OSD | [quantumgizmos/ldpc](https://github.com/quantumgizmos/ldpc), with a C++ core and Python bindings |
| Published beam-search baseline | [ionq-publications/BeamSearchDecoder](https://github.com/ionq-publications/BeamSearchDecoder), with `decoder/src_cpp/beam_search.hpp` and native Python bindings |
| BB construction and circuit reference | [sbravyi/BivariateBicycleCodes](https://github.com/sbravyi/BivariateBicycleCodes), particularly `decoder_setup.py` |
| Reusable BB code and Stim memory-circuit implementation | [qLDPCOrg/qLDPC](https://github.com/qLDPCOrg/qLDPC), including `BBCode`, `circuits.get_memory_experiment`, and circuit noise utilities |
| Circuit sampling and detector models | [quantumlib/Stim](https://github.com/quantumlib/Stim) |
| DEM converter comparison/reference | [oscarhiggott/stimbposd](https://github.com/oscarhiggott/stimbposd) |

The beam repository supplies pre-generated circuits for other code instances, including BB144 and BB90. Do not assume it contains the required BB72 circuit, or relabel one of those files as BB72. Its matrix-level native decoder accepts a check matrix and a channel-probability vector, which permits all three decoders to receive the same prepared problem.

The inspected beam implementation exposes `max_rounds`, `beam_width`, `num_results`, `initial_iters`, and `iters_per_round`. Its native BP uses a min-sum update; do not assume generic `ldpc` keyword arguments such as `bp_method` can be forwarded. Inspect the pinned binding and test accepted parameters. Preserve the published baseline's numerical and tie-breaking conventions.

The [beam-search paper](https://arxiv.org/abs/2512.07057) uses a BP-OSD comparison with 30 min-sum iterations and order-10 combination-sweep OSD. Use this as a documented initial baseline profile, not as evidence that the profile is optimal for these requested circuits.

Maintain a development fork of `ldpc` under `external_lib/ldpc/`, with an `upstream` remote and a dedicated branch such as `screened-decimation-bp`, based on the pinned upstream commit. Use the user's fork remote if available. A local development fork/branch can support the implementation if a hosted fork is unavailable; explicitly record that state. Creating a hosted fork is not a reason to stop local implementation or testing. Do not publish commits as part of these prompts.

Add the required BP functionality as an explicit opt-in interface. Existing BP-OSD behavior must remain unchanged when the new interface is unused. Test this against a pristine pinned upstream build or an equivalent independently installed reference environment. Do not let the experiment accidentally import an unrelated system installation of `ldpc`.

Keep the published beam implementation as its own baseline. Project-owned screening/search code must be written independently in C++. Do not replace the baseline with a reimplementation or transplant its search code into the new decoder. Retain external notices and record licenses and local patches in the dependency manifest.

For each dependency, record URL, commit, relevant paths, build command, compiler/options, import location, version, local changes, and the scientific role it performs. Pin package/build dependencies as well as repository sources.

## D. Circuits, noise, and decoder input

### D.1 Circuit providers

For the rotated surface code, use Stim's `surface_code:rotated_memory_z` generator with `rounds=d`. Generate an initially noiseless circuit for the shared noise-injection profile described below.

For BB72, use a pinned external implementation rather than inventing a code or syndrome-extraction schedule. The default route is `qLDPC`'s BB construction and Z-basis memory generator. Check its circuit construction against its source and tests, and document its actual syndrome-extraction strategy. A library edge-coloring schedule must be identified as that schedule, not described as the original paper's optimized seven-layer CNOT schedule.

The BB72 algebraic parameters are

\[
\ell=m=6,\qquad
A_{\mathrm{BB}}=x^3+y+y^2,\qquad
B_{\mathrm{BB}}=y^3+x+x^2,
\]

with \(x^\ell=y^m=1\). Confirm the matrix convention against the pinned implementation and the [original BB source](https://github.com/sbravyi/BivariateBicycleCodes/blob/main/decoder_setup.py). Validate 72 data qubits, 12 logical qubits, CSS commutation, and the logical-operator basis over \(\mathbb F_2\).

Record the published code distance as 6. This does not certify that an arbitrary circuit schedule has circuit distance 6. Do not claim a circuit-distance proof from rank checks or a small fault sample.

Inspect what the circuit provider counts as a round. Save initialization, repeated noisy extraction, and destructive final readout conventions. Do not silently add the original BB repository's extra ideal closing cycles to an experiment labeled six rounds. If a provider requires an additional boundary operation, identify it explicitly and retain the requested number of noisy extraction rounds.

### D.2 Shared circuit-noise profile

Use one explicit circuit-depolarizing rule set for both families. Prefer the pinned `qLDPC` noise utilities applied once to the noiseless Stim circuits; validate their behavior rather than assuming their defaults.

For physical sweep value \(p\), define five YAML multipliers, initially all one:

- \(p_{1q}=\mu_{1q}p\): one-qubit depolarization after a one-qubit Clifford gate;
- \(p_{2q}=\mu_{2q}p\): two-qubit depolarization after a two-qubit Clifford gate;
- \(p_{\mathrm{idle}}=\mu_{\mathrm{idle}}p\): one-qubit depolarization on idle qubits in each defined circuit moment;
- \(p_{\mathrm{reset}}=\mu_{\mathrm{reset}}p\): reset to the wrong eigenstate;
- \(p_{\mathrm{meas}}=\mu_{\mathrm{meas}}p\): measurement-outcome flip.

In particular, enable idle noise explicitly; the inspected `DepolarizingNoiseModel` does not enable it by default. A configurable `NoiseModel` is appropriate when the five probabilities differ.

Specify the timing of resets, measurements, combined measurement/reset operations, and `TICK` boundaries. Verify that idle errors are neither duplicated nor omitted. Apply noise to preparation and final readout as well as extraction unless an explicitly named alternative profile specifies otherwise. Respect the provider's qubit allocation and annotate the exact eligible idle-qubit set.

Do not simultaneously enable Stim-generated noise and apply the external noise injector. Save an operation/noise inventory and the final noisy circuit bytes for every scientific instance. All decoders for an instance use exactly those bytes.

This is a reproducible circuit-level benchmark using published software. It is not automatically a reproduction of the original BB paper's complete noise/schedule convention.

### D.3 Single-sector detector selection

Construct a verified mapping from detector IDs to their check sector and time/boundary role. Use provider bookkeeping, measurement-record relations, or a validated circuit annotation, not a guessed coordinate parity.

Retain the Z-check detector rows for the default decoder input and all logical Z observables. Keep all physical extraction operations in the sampled circuit. If other-sector detector annotations complicate DEM extraction, omit those annotations in a decoding-view circuit while preserving every physical operation and observable annotation.

Save the full-to-selected detector-index map. Test that projecting full sampled detector records agrees with sampling or deriving the equivalent selected detector view. Do not append the sampled true observable outcomes to any decoder input.

### D.4 Canonical detector problem

All decoders must receive the same canonical binary problem:

\[
H e=s,\qquad \hat y=Ae,\qquad
w_i=\log\frac{1-p_i}{p_i}.
\]

Here \(e_i\) denotes a DEM error mechanism. It is not necessarily a physical qubit error. In particular, the screened decoder's \(U\) contains DEM-column indices, not BB data-qubit indices. The mechanism prior \(p_i\) must not be replaced by the physical sweep parameter \(p\).

Extract an undecomposed DEM with graphlike decomposition disabled. Keep hyperedges. Do not silently enable `approximate_disjoint_errors` or gauge-detector approximations to make conversion succeed. Any requested approximation must be an explicit YAML option, recorded with its effect on the model.

Implement or validate the converter with these requirements:

- Expand repeat/offset semantics correctly.
- One DEM error instruction represents one Bernoulli mechanism. Separator components inside that instruction remain correlated and must not become independent variables.
- Build detector and observable supports using parity/XOR semantics.
- Preserve columns with no selected detector support but nonzero observable support.
- Keep deterministic column ordering and an instruction-to-column map.
- Default to retaining separate DEM instructions; do not introduce an extra project-level column-merging heuristic.
- If a supported optional merge is implemented, only merge identical joint detector-and-observable signatures under an appropriate independence assumption, using \(p_{\mathrm{odd}}=[1-\prod_j(1-2p_j)]/2\). Never merge solely because detector supports match.
- Handle zero-probability mechanisms by exact removal and maintain reconstruction maps. Deterministic mechanisms or complemented variables, if supported, require both syndrome and observable offsets. Otherwise reject unsupported probabilities explicitly.

The noiseless \(p=0\) validation path must work, including a model with zero stochastic columns. It may short-circuit before constructing a positive-depth decimation search. Do not relax the core algorithm's validation of \(q\).

Hash and persist \(H,A,p_i\), the DEM, mappings, and extraction options. A direct use of a third-party converter is acceptable only after tests establish these semantics.

## E. Proposed decoder and baseline profiles

The following is a consistency checklist; the complete algorithm specification remains normative.

1. Initial synchronous flooding sum-product BP, with iteration-zero syndrome checking.
2. If it fails, construct \(U\) once from the last \(W_{\mathrm{hist}}\) completed posterior iterations:
   \[
   r_i=\left|\frac{1}{W_{\mathrm{eff}}}\sum_t L_i^{(t)}\right|,
   \qquad
   o_i=\sum_t\mathbf1[\mathbf1(L_i^{(t)}<0)\ne\mathbf1(L_i^{(t-1)}<0)].
   \]
   Select the first \(\min(M,n)\) variables under \((r_i,-o_i,i)\).
3. Enumerate every \((F,b_F)\) with \(F\subseteq U\), \(|F|=q\), and all binary assignments.
4. Form \(s_D=s\oplus H_Fb_F\), structurally remove all fixed columns, reject odd degree-zero checks, and score without running BP:
   \[
   g(D)=\sum_{i\in F}w_i b_i,\quad
   R_D=\{a:(s_D)_a=1\},\quad
   k_j(D)=|\mathcal N(j)\cap R_D|,
   \]
   \[
   h(D)=\sum_{a\in R_D}
   \min_{\substack{j\notin F\\H_{aj}=1}}\frac{w_j}{k_j(D)},
   \qquad f(D)=g(D)+h(D).
   \]
   The bound uses all free variables, including variables outside \(U\).
5. Retain the exact top \(K\) patterns ordered by \(f(D)\), then \(\sum_{i\in F}r_i\), then the canonical pattern ID.
6. Cold-start the same flooding BP kernel on each selected residual graph. Evaluate all selected patterns.
7. Reconstruct and validate complete corrections. Select minimum physical cost, then lexicographic correction bits, among successful completions. Otherwise return an explicit failure.

The score is a lower bound on physical completion cost, not a calibrated convergence probability. Its real-arithmetic proof does not make binary64 comparisons a certified optimality test.

Default screened-decoder settings:

| Parameter | Initial value |
|---|---|
| Initial BP iterations \(T_0\) | 30 |
| Completion BP iterations \(T_{\mathrm{post}}\) | 30 |
| History window | 8 |
| Candidate-pool size \(M\) | 16 |
| Fixed depth \(q\) | 2 |
| Completion count \(K\) | 8 |
| LLR clip magnitude | 25 |
| BP method | Sum-product |
| BP schedule | Synchronous flooding |
| Arithmetic | Binary64 |
| Damping / warm start / fallback | Disabled |

The BP implementation must match the specification's buffers, update barriers, syndrome sign, clipping locations, ascending summation order, degree-zero/one rules, and decision rule \(L<0\). In particular, compute extrinsic messages from the prior and incoming check messages, not by subtracting from an already clipped posterior.

“Parallel BP” denotes the flooding update schedule. It does not require multiple CPU threads. Default single-shot measurements use one native thread; independent shots are distributed across worker processes.

BP must execute inside the modified `ldpc` C++ implementation. Add an opt-in native API for the required history, status, and decimation behavior. A separate Python BP implementation is allowed only as a small test oracle. All candidate selection, enumeration, scoring, top-\(K\) handling, decimation orchestration, and completion selection execute in project-owned C++. Avoid a Python callback for each candidate or BP iteration.

Provide these named configurations:

- `screened_reference`: the settings above.
- `bposd_ms30_cs10`: `minimum_sum`, parallel schedule, 30 iterations, scaling factor explicitly 1.0, `OSD_CS`, order 10, one native thread; verify the exact accepted API names.
- `beam8`: upstream native kernel, `max_rounds=10`, `beam_width=8`, `initial_iters=30`, `iters_per_round=20`, `num_results=1`.
- Optional configuration examples, disabled by default: `beam32` with width 32, initial iterations 40, iterations per round 30, maximum rounds 10, and one result; and a sum-product BP-OSD profile for a more closely matched BP-kernel comparison.

The initial comparison is between complete configured decoders. Different BP kernels and budgets must remain visible in metadata and figure labels; they do not isolate the effect of screening alone.

Do not pass nonexistent options to the native beam decoder. Upstream fixed conventions can be exposed in resolved YAML/JSON as validated implementation properties; changing them requires a separately named variant. No unsupported parameter may be silently ignored.

## F. YAML configuration contract

Use a strict schema with unknown-field rejection, useful validation errors, and no arbitrary code evaluation. Resolve relative paths against the directory containing the configuration file. All resolved paths and expanded parameter grids must be saved.

At minimum, the schema must cover:

| Group | Required settings |
|---|---|
| Experiment | Name, purpose, code families, distances, memory basis, sector, round rule/override |
| Noise | Profile, physical-rate list or explicit linear/log sweep, all noise multipliers |
| Circuit | Provider, schedule, boundary conventions, generation/cache locations |
| DEM | Extraction options, sector mapping, normalization/merging policy |
| Decoders | Enabled instances and every supported algorithm parameter |
| Sampling | Shots per point, batch size, master seed, warmup seed/count, raw-sample storage |
| Execution | Worker count, spawn mode, bounded pending tasks, worker cache size, native thread limits, affinity |
| Timing | Timing mode, timer fields, warmup, decoder execution order, profiling level |
| Output | Root path, table compression, shard policy, trace/correction retention |
| Analysis | Confidence level, quantiles, plot options, input/output paths |

Provide:

- `config/smoke.yaml`: a small runnable configuration, with \(p=10^{-3}\) clearly marked as an implementation example.
- `config/latency_smoke.yaml`: a single-worker timing run.
- `config/production_template.yaml`: user-editable production settings, with an empty physical-rate grid that cannot be run accidentally.
- A compact decoder-configuration sweep example.

Do not supply an invented production sweep as if the user had selected it. Permit both explicit rate lists and well-defined linear/logarithmic grids; choose exactly one specification per sweep, reject duplicates, and save expanded values.

Separate identities:

1. Scientific-instance identity: code, circuit, noise, rounds, basis, selected detectors, DEM conventions, and associated artifact hashes.
2. Decoder identity: implementation revision and fully resolved decoder parameters.
3. Sampling-plan identity: master seed, immutable batch layout, Stim version, and sampling-call convention.
4. Run identity: timestamp and execution/output configuration.

Changing the decoder list or worker count must not change the physical samples for a fixed scientific instance and sampling plan. Do not use display strings rounded to 12 significant digits as the sole scientific identity.

## G. Sampling, timing, and parallel execution

Adapt the supplied modules' useful structure:

| Supplied file | Reuse concept | Replace project-specific behavior |
|---|---|---|
| `config.py` | Immutable task descriptors; stable batch IDs and seed derivation | Hard-coded code-capacity grid, one-round assumptions, path constants |
| `parallel_runner.py` | `ProcessPoolExecutor`, `spawn`, lazy tasks, bounded pending futures | Fixed worker function and old task/result types |
| `sampling.py` | Sample a physical batch once; apply every decoder to that batch | Color-code objects, comparative decoding, swim-distance calculations |
| `pairing.py` | Validate physical-record and annotation mappings | Forced observable appended as a detector; one-observable assumptions |
| `storage.py` | Explicit Arrow schema; semantic validation; atomic Parquet shards | Old wide schema, hard-coded metrics, indiscriminate nonnegative-float assumptions |
| `provenance.py` | Source hashes; repository/environment metadata; atomic JSON | Old dependencies, source paths, experiment claims |

Do not import unrelated color-code or soft-output packages into the new benchmark.

Generate immutable batch tasks before scheduling. Give each shot a stable identity within its scientific instance. Sample once per task, retain detector and actual-observable arrays, and decode exactly the same selected syndrome for every enabled decoder.

Use a documented deterministic seed derivation, such as the supplied SHA256-to-little-endian-uint32 plus NumPy `SeedSequence` construction. Include a stream tag to separate sampling, warmup, and any decoder randomness. Never use Python's randomized `hash()`, wall time, worker ID, or completion order to seed physical shots.

Stim's exact random stream can depend on version, sampling-call shape, and execution platform. Require reproducibility for a fixed pinned environment and fixed batch plan; do not promise invariance to changing batch size or Stim version. Storing packed raw samples enables exact decoder replay even when resampling is not bitwise portable.

Use `spawn` workers and no decoder object transfer between processes. Construct native objects inside the worker, with a bounded cache keyed by immutable problem/configuration identity. Reuse allocation only when all syndrome-dependent state is reset before the next shot.

Default maximum in-flight tasks is twice the worker count, configurable. Use a single parent-side writer for returned batches. Exceptions propagate, pending tasks are cancelled where possible, and successfully written shards remain readable. Do not accumulate all shots in memory.

Provide two execution modes:

- `throughput`: configurable multiple workers, default four, one native thread per worker. Record both timing fields, marking wall times as measured under concurrent load.
- `isolated_latency`: one worker, one native thread, optional explicit CPU affinity. Use this profile for the primary single-shot latency-distribution comparison.

Control OpenMP/BLAS threads before importing numerical/native packages, and save effective thread settings. A thin bootstrap can parse YAML and set the environment before importing the numerical implementation. Reject or explicitly label oversubscribed settings.

For every shot/decoder, record integer nanoseconds from both `time.process_time_ns()` and `time.perf_counter_ns()`:

- CPU time measures process CPU consumption.
- Wall time measures elapsed decode-call latency and includes scheduling delays.

The timed decoder operation includes required per-shot reset, input adaptation, initial BP, candidate construction/scoring, candidate-specific graph work, postprocessing, correction reconstruction, syndrome validation, and observable prediction. Exclude circuit generation, DEM extraction, decoder construction, sampling, interprocess queues, output serialization, and plotting. Record setup times separately. Shared preprocessing must not hide work that actually depends on the syndrome or selected pattern.

Use a dedicated warmup stream. Exclude warmup shots from LER and latency tables. Reset the decoder after warmup. Use a deterministic cyclic decoder order based on shot identity, optionally configurable, and record that policy.

Measure every shot, including zero-syndrome shots, initial-BP successes, postprocessing successes, and decoder failures. Do not report only successful or difficult cases as an unconditional latency distribution. Do not use batched throughput divided by shot count as an individual latency measurement.

Record timer overhead/resolution as diagnostics without subtracting a potentially noisy estimate from each result. Detailed internal phase profiling is optional and separately labeled; it must not be mixed with minimally instrumented primary timing.

## H. Storage and reproducibility

Create a new run directory under the YAML output root using a timezone-aware UTC timestamp with subsecond precision and a collision-resistant suffix. Use exclusive directory creation. Each scientific instance gets its own subdirectory, whose name contains a readable label plus a hash.

A suitable organization is:

```text
assets/runs/<utc_timestamp>_<run_id>/
    manifest.json
    config_original.yaml
    config_resolved.json
    environment.json
    source_provenance/
    instances/<scientific_instance_id>/
        instance.json
        circuit.stim
        detector_model.dem
        matrices/
        detector_mapping.json
        observable_mapping.json
        samples/part-<batch_id>.parquet
        decodes/part-<batch_id>.parquet
        batch_manifests/
    summaries/
    figures/
    logs/
```

This is a data-layout specification, not a request to hard-code output paths. Circuits or matrices shared with `simulation_data/` may be copied or referenced by content hash, provided a completed run remains reproducible and its referenced bytes are retained.

Use long-form decoder results: one row per scientific instance, shot, and decoder configuration. Store physical samples once per shot, with explicit little-endian packing for detector bits if packed storage is enabled. Retain all observable outcomes and predictions with their mapping. Raw selected detector storage is enabled by default.

Define and version Arrow schemas. At minimum, preserve:

- run, instance, sampling-plan, batch, shot, and decoder identities;
- code family, distance label, \(n\), \(k_Z\), rounds, physical \(p\), and noise-profile identity;
- actual observable vector in the sample table;
- predicted observable vector or explicit null on decoding failure;
- normalized status, native status where available, syndrome-validity flag, and failure/mismatch fields;
- CPU and wall decode times;
- available BP iteration and search counters, with unavailable values null rather than fabricated;
- screened-decoder initial-success flag, candidate counts, rejection counts, BP-completion count, selected pattern, and successful correction cost;
- source/model/configuration hashes needed to join results safely.

Optional large traces and full correction vectors must be controlled by YAML. Required internal LLR-history computation remains enabled for the proposed algorithm even when diagnostic trace storage is disabled.

Distinguish a legitimate null result from a missing/incomplete row. Do not store NaN or infinity as fake costs for failed decodes. JSON must be standards-compliant with nonfinite values rejected.

Write shards through temporary files and atomic replacement on the same filesystem. Never overwrite an existing committed shard. Record batch row counts and checksums; mark a batch committed only when its paired sample/result files are complete. A run is complete only when every expected task/decoder result exists.

Resumption is not required for the initial implementation. An interrupted run must remain marked incomplete; a new attempt uses a new timestamped directory. Do not claim resumption support without implementing and testing duplicate prevention, configuration compatibility, and partial-batch recovery.

The manifest must capture the full resolved experiment, numerical conventions, source revisions and dirty patches, relevant source hashes including C++/Cython/build files, dependency lock, compiler/build flags, native module paths, Python environment, platform/CPU/affinity/thread settings, seed recipe, immutable task list or its reproducible description, artifact checksums, and run status.

Support repositories whose `.git` is a file, as in a worktree. Preserve dirty patches and relevant untracked first-party source bytes when needed for reproduction. A hash alone does not preserve modified source content.

## I. Analysis and documentation

Implement reusable analysis functions; notebooks should select data and invoke them rather than contain duplicated simulation or statistical logic.

Initial outputs:

- Z-memory block failure rate versus physical error rate for each code/distance and decoder configuration;
- decoding-failure and valid-output logical-mismatch components;
- 95% Wilson intervals by default, with confidence level configurable;
- CPU-time and wall-time ECDFs or survival curves;
- mean, median, p90, p95, p99, p99.9, and maximum decode time;
- timing summaries separated by execution mode and optionally by initial-BP success, postprocessing, or failure.

Do not pool different code instances, noise profiles, worker/thread modes, or decoder configurations unless explicitly requested. Aggregate LER by summing failure and shot counts, not by averaging batch rates.

For zero observed failures, show an uncertainty bound rather than an artificial positive point on a log axis. For tail quantiles, report sample size and expected tail count \(N(1-q)\), and mark small-sample tail estimates as insufficient for a performance claim. A smoke run is a software validation, not a decoder-performance result.

Do not treat the 12 BB observables as independent Bernoulli trials for a block-level confidence interval. If reporting an average per-observable quantity with uncertainty, account for within-shot dependence.

Document installation, external forks, clean native builds, configuration fields, circuit/noise/sector conventions, decoder profiles, timing methodology, schemas, reproducibility, CLI commands, notebook use, extension points, and known limitations. Include a specification-to-implementation-to-test traceability table.

## J. Required verification principles

Tests must validate behavior against independent expectations, not merely repeat implementation branches.

Required examples include:

- a scalar flooding-BP oracle and hand-computable parity systems;
- exact small-problem enumeration for the screening lower bound and top-\(K\) ordering;
- structural fixed-zero/fixed-one behavior and reconstruction;
- detector/observable parity mappings, including separator and logical-only DEM events;
- \(p=0\) circuits and 12-observable BB readout;
- same-shot delivery to all decoders and no truth leakage;
- one-worker versus multiple-worker equality of non-timing results for a fixed batch plan;
- fresh-object versus reused-object decoding and shot-order permutation;
- Arrow/Parquet round-trip, null semantics, exact identifiers, and interrupted-run status;
- unmodified upstream BP-OSD regression with the fork extensions disabled;
- direct upstream beam decoding versus the adapter on the same matrices/syndromes.

Do not require different decoders to return the same correction: degeneracy permits different valid outputs. Compare syndrome validity and logical predictions where equality is part of the tested contract.

Use finite, small CI fixtures. Keep long statistical simulations out of the unit suite. Test native code in a debug/sanitizer configuration where supported and benchmark only an optimized build without fast-math transformations that change the specified arithmetic.

## Prompt 1 — Bootstrap, contracts, configuration, and dependency audit

```text
Implement Stage 1 of the QEC BP benchmark package.

Read codex_bp_benchmark_implementation_prompts.md completely. Its Sections A–J are the project contract for all stages. Read bp_decimation_screening_specification.md and the six supplied reference Python modules. Locate supplied files by their basenames if their attachment paths differ; do not confuse those reference modules with new package modules.

Create the requested repository layout and a working installable Python/C++ project skeleton. Preserve existing user work and applicable instructions. Create AGENTS.md and STATUS.md, and copy the supplied algorithm specification into docs/ without changing its scientific content. Preserve the reference modules in a clearly labeled reference directory; do not install them as the new implementation.

Write docs/benchmark_contract.md documenting the resolved circuit, Z-memory sector, observable, failure, timing, pairing, and storage conventions from the project contract. Write docs/architecture.md with module responsibilities and interfaces. These documents must guide subsequent implementation.

Implement the strict YAML configuration model and validation. Include all parameter groups, named decoder profiles, explicit physical-rate sweep expansion, path resolution, and separate scientific/decoder/sampling/run identities. Supply smoke, isolated-latency smoke, and production-template YAML files. The production template must not execute with an empty physical-rate grid. Do not launch production simulations.

Inspect and pin the actual upstream dependencies and their APIs. Establish the ldpc development fork/branch with an upstream remote, and maintain the beam baseline separately. Compile/import the unmodified native dependencies now. Record exact versions, commit hashes, compiler flags, import paths, supported parameter names, fixed conventions, and local patches in external_lib/manifest.lock.json and docs/dependency_audit.md.

Confirm the BB72 construction and usable qLDPC memory/noise APIs. Record that the default qLDPC extraction schedule is not automatically the original BB paper's optimized schedule. Confirm the native beam decoder's actual constructor rather than copying a wrapper's possibly outdated docstring. Never silently substitute another code or another decoder.

Create a minimal build/import test for the project's native extension, configuration/identity tests, and unknown-parameter rejection tests. Test changes incrementally, including native compilation. If a dependency cannot be obtained or built, continue all independent work, record the exact failure and affected features, and do not replace missing functionality with fabricated outputs or mark the gate passed.

End this stage with runnable install/build commands, passing available Stage 1 tests, current module READMEs, and an accurate STATUS.md. Report the files changed, commands actually run, and any remaining blocker. Do not proceed to Stage 2 in this response.
```

## Prompt 2 — Circuit providers, sector mapping, DEM conversion, and fixtures

```text
Implement Stage 2 in the existing benchmark repository.

Read AGENTS.md, STATUS.md, docs/benchmark_contract.md, the dependency audit, and Sections A–J of codex_bp_benchmark_implementation_prompts.md. Preserve the algorithm specification and the Stage 1 configuration contract.

Implement the rotated-surface and BB72 circuit providers. Defaults are surface distances 5, 7, and 9 with R=d, and BB [[72,12,6]] with R=6. Use the pinned external providers. BB72 must expose all 12 logical Z observables. Validate CSS checks and the logical basis with independent GF(2) calculations.

Implement the common configurable circuit-depolarizing profile on noiseless circuit templates, including explicitly enabled idle noise. Preserve both sectors' physical extraction operations. Save the exact schedule, boundary convention, noise-operation inventory, and generated Stim bytes. Avoid duplicate noise injection.

Implement and test Z-check detector selection using verified measurement/bookkeeping information. Produce detector and observable maps and a selected decoding view with identical physical operations. Do not give true observable outcomes to a decoder.

Implement the canonical undecomposed DEM-to-(H,A,p) conversion, deterministic column order, normalization maps, and artifact hashes. Preserve hyperedges, logical-only columns, repeat offsets, and correlations between separator components. Do not merge columns by detector support alone or silently enable approximations. All decoders will consume this same canonical object.

Create small saved fixtures under simulation_data/ and tests/fixtures/. Test noiseless circuits, all requested default code instances, six-round BB memory, 12-observable dimensions, repeat/offset and separator cases, same-detector/different-observable mechanisms, and exact matrix-parity identities. Use controlled single-fault or small exhaustive fixtures for converter checks; statistical agreement alone is not an adequate converter test.

Provide a thin python_scripts entry point and shell launcher for preparing/validating circuit artifacts from YAML. Rebuilding an unchanged instance in the pinned environment must reproduce its circuit and matrix hashes, or any upstream nondeterminism must be removed or explicitly frozen in the saved artifact.

Document the provider schedule and circuit-distance limitations accurately. Complete the circuit/noise/DEM module READMEs, update STATUS.md with actual test results, and stop after the Stage 2 gate. Do not substitute a generic phenomenological model when a circuit test fails.
```

## Prompt 3 — Forked ldpc flooding-BP kernel and native interface

```text
Implement Stage 3: the reference flooding-BP functionality inside the ldpc fork.

Read the current project instructions/status, the algorithm specification, and the benchmark contract. Inspect the pinned ldpc C++ implementation before editing it.

Add an opt-in native interface that implements the exact sum-product flooding kernel from the specification and supports the initial-run posterior history needed by candidate selection. Preserve ordinary upstream APIs and defaults. If upstream clipping, zero-LLR ties, degree-one handling, or stopping behavior differs from the specification, implement those differences only in the new explicit reference profile.

Use previous-iteration variable-message buffers for the complete check half-step, then the completed new check messages for the variable half-step. Preserve the exact syndrome sign, iteration-zero check, clipping locations, ascending accumulation order, binary64 arithmetic, L<0 hard-decision convention, and degree-zero/degree-one rules. Never calculate an extrinsic message by subtracting from a clipped posterior.

Support exact structural decimation through a residual graph or a semantically equivalent active-column mask with syndrome adjustment. Fixing zero removes its edges just as fixing one does. Finite large-prior clamping is not an implementation of structural fixation. Every candidate completion cold-starts from the original physical priors.

Expose native status, completed iteration count, final correction/beliefs, and the last requested history window or sufficient equivalent statistics. Required history computation must remain native and must not invoke Python once per iteration. Keep diagnostic full traces optional. Expose build/source identity so the main package can prove it loaded the intended fork.

Implement a small independent scalar Python oracle under tests/, not in the production decoder. Compare complete short iteration traces and outputs against the C++ kernel. Cover zero syndrome, a one-variable odd check with unsaturated prior, degree-zero contradictions, zero messages, LLR saturation, isolated variables, history-window endpoints, fixed bits, reset/reuse behavior, and simultaneous-update semantics.

Run focused C++ tests, Python binding tests, and a sanitizer/debug build where supported. Check a representative set of ordinary BP-OSD outputs against pristine pinned upstream with the new features disabled. Fix regressions before continuing.

Record the fork diff, API, ownership/reset rules, and build commands in the integration documentation and module READMEs. Update STATUS.md with test evidence, and stop after Stage 3. Do not yet implement a Python production search loop or change the published beam decoder.
```

## Prompt 4 — C++ screening/search and the three decoder adapters

```text
Implement Stage 4: the complete screened-decimation decoder and baseline adapters.

Read the project contract and the complete algorithm specification. Use the Stage 3 ldpc native BP interface. All project-owned candidate selection, pattern enumeration, scoring, top-K retention, decimation orchestration, and final correction selection must be implemented in C++. Python may configure and call the decoder but must not execute a per-pattern or per-iteration loop.

Implement the exact reference algorithm: static U ranked by absolute mean posterior LLR, negative flip count, and index; all size-q subsets and all binary assignments; structural residual syndrome/graph; zero-degree contradiction filtering; the weighted completion lower bound using all free variables; deterministic top-K selection; cold-start BP on every retained candidate; and final minimum physical cost with lexicographic tie-breaking.

Keep physical weights unclipped. Do not substitute posterior reliability for physical cost. Do not stop after the first successful postprocessing candidate. Do not add degree-one screening propagation, adaptive q/M/K, warm starts, or a fallback decoder. A bounded top-K heap is acceptable if it produces exactly the same retained ordered list as exhaustive sorting.

Add a thin Python binding and a common decoder-result interface with correction, prediction, validity, normalized/native status, cost, counters, and optional diagnostics. Use a single prepared canonical (H,A,p) problem for all adapters.

Integrate BP-OSD through the unchanged upstream-compatible interface in the fork. Integrate the actual published native BeamSearchDecoder through its matrix interface, preserving its native numerical conventions. Test accepted parameters; reject ignored/unknown settings. The BP-OSD converge flag may refer only to its BP stage, so independently validate the final correction after OSD. Likewise validate beam outputs against H e=s. Do not fabricate a successful prediction after an exhausted search.

Test each component as it is added. Use exact small-system enumeration to check score lower bounds, candidate counts, canonical IDs, tie-breaking, and selected top-K lists. Reproduce the specification's worked example. Exercise initial-BP success, rescue by a non-default fixed value, no selected completion success, multiple successful completions with different costs, fixed-zero behavior, and reconstructed syndrome validity.

Compare the C++ complete decoder with a small test-only reference orchestrator. Compare the beam adapter directly with the pinned native decoder and the BP-OSD adapter with its native API. Test fresh versus reused objects, different shot orders, and no cross-candidate/shot state leakage. Different algorithms need not return identical corrections.

Document the difference between flooding schedule and CPU multithreading, all supported YAML parameters, fixed upstream conventions, and timing-relevant allocations. Update native/module READMEs and STATUS.md with actual build/test results. Stop at the Stage 4 gate.
```

## Prompt 5 — Paired multiprocess simulation, timing, Parquet, and provenance

```text
Implement Stage 5: the executable simulation pipeline.

Read the benchmark contract and the supplied reference modules again only as needed. Adapt their immutable BatchTask, deterministic seed, spawn-process, bounded-future, atomic-shard, and provenance patterns. Remove all assumptions specific to the earlier color-code/soft-output study.

Implement a lazy immutable task stream and deterministic sample plan. Sample each physical batch once and pass the same selected syndromes to every enabled decoder. Store all actual logical Z outcomes separately from decoder inputs. Decoder lists, worker count, completion order, and output location must not alter samples under a fixed instance and sampling plan.

Implement spawn-based ProcessPoolExecutor scheduling with configurable workers and bounded pending tasks, a serial path for one worker, bounded worker-local caches, and parent-side storage. Reset all per-shot decoder state. Set effective native/BLAS thread limits from YAML before importing numerical/native libraries.

Implement throughput and isolated_latency modes exactly as specified. Warm up on a separate seed stream and use deterministic cyclic decoder order. Record per-shot process CPU time and wall time around the complete per-shot decode service. Include screening, candidate-specific graph work, postprocessing, validity checks, and observable prediction; exclude sampling/setup/queues/I/O. Record setup separately. Preserve failure-shot times and label concurrent-load timings correctly.

Implement versioned Arrow schemas for samples and long-form decoder results, with all 12 BB observables retained. Use explicit nulls for unavailable diagnostics and missing predictions. Compute block failure and logical-mismatch labels according to the contract. Unexpected exceptions must fail the task/run rather than become simulated logical errors.

Implement timestamped run and per-instance directories, atomic paired batch shards, batch checksums/counts, complete JSON reproducibility metadata, original/resolved configurations, circuit/DEM/matrix artifacts, and source/build/environment provenance. Never overwrite existing committed outputs. Preserve dirty patches/source content and handle Git worktrees. Mark interrupted runs incomplete; do not claim unimplemented resume support.

Provide thin python_scripts/run_benchmark.py and scripts/run_benchmark.sh entry points accepting a YAML path. Shell scripts must not duplicate scientific parameters. Add a saved-sample replay entry point so the same physical dataset can be decoded with another YAML decoder configuration.

Test deterministic non-timing equality with one and two workers; reordered task completion; final short batches; warmup isolation; decoder-input pairing; no truth leakage; failure labels; worker exceptions; bounded scheduling; Parquet round-trip; uint64 seed fidelity; duplicate-output protection; and incomplete-run recovery/readability.

Run a small end-to-end three-decoder simulation using real native backends, not mocks. Update runner/storage/provenance READMEs, CLI documentation, and STATUS.md. Stop after the Stage 5 gate; do not start a production sweep.
```

## Prompt 6 — Analysis modules, notebooks, and complete documentation

```text
Implement Stage 6: reusable analysis and user documentation.

Read the stored schema and benchmark conventions. Implement analysis/ modules for discovering runs, validating manifests, loading/selecting paired Parquet data, aggregating failure counts, computing Wilson intervals, summarizing timing quantiles, and producing figures. Keep experiment logic out of notebooks.

Provide plots of Z-memory block failure rate versus p for each code/distance and decoder, with decoding-failure information available separately. Provide CPU-time and wall-time ECDF/survival plots and summaries of mean, median, p90, p95, p99, p99.9, and maximum. Do not mix isolated and concurrent timings.

Respect the 12-observable BB block definition. Do not divide block error by 12, multiply a sector rate by two, pool dependent observables as independent shots, or equate block time/R with measured online round latency. Use summed counts rather than averaged batch rates. Handle zero failures and low sample counts explicitly, and annotate insufficient tail statistics.

Create notebooks under notebook/ that read manifest-selected datasets and call the analysis modules. No decoder implementation, hidden simulation, or hard-coded workstation paths should appear in a notebook. Make a notebook runnable against the small Stage 5 output and export its initial figures.

Complete detailed documentation: setup/build, external fork maintenance, architecture, complete YAML reference, circuits/noise/boundaries/sector, decoder profiles, timing methodology, output schema, reproducibility/replay, testing, and extension points. Add the specification-to-code-to-test traceability table. Every first-party module directory must have an accurate implementation README.

Test analytical results against hand-computable synthetic tables, including zero failures, failed decodes, missing diagnostics, multiple observables, incomplete runs, incompatible configuration mixes, and exact quantiles. Execute the notebook against smoke data. A successful smoke plot must not be described as evidence of decoder superiority.

Update AGENTS.md with stable maintenance commands and STATUS.md with actual outcomes. Stop at the Stage 6 gate.
```

## Prompt 7 — Clean-build acceptance and implementation handoff

```text
Perform Stage 7: final acceptance of the implemented benchmark package.

Read the full project contract, AGENTS.md, STATUS.md, the algorithm specification, and the implementation/test traceability table. Audit the delivered code against the requested scope rather than relying on earlier completion claims.

Build the package and all required native dependencies from the recorded pinned sources in a clean environment. Verify imported native-module paths and build identities. Run the required focused tests, relevant upstream regressions, native debug/sanitizer checks where supported, and complete integration tests. Benchmark runs must use optimized builds.

Run small fixed-seed end-to-end cases for surface d=5,7,9 and BB [[72,12,6]], all with R=d, circuit-level noise, one Z-memory sector, and all enabled decoder baselines. Include one-worker and two-worker runs and an isolated-latency smoke run. Verify non-timing result equality for identical sample plans and correct 12-observable BB data.

Audit that the proposed decoder uses the exact static-U/exhaustive-screening algorithm and forked ldpc flooding BP, that all new search work is native C++, and that the published beam baseline has not been silently replaced or retuned through ignored parameters.

Audit every default and exposed setting against YAML and resolved metadata; inspect timing boundaries, thread settings, raw sample pairing, failure denominators, DEM hyperedges, observable mapping, artifact hashes, committed shard completeness, and source preservation. Verify the production template refuses to run until the user supplies a physical-rate sweep.

Execute the documented build/run/analyze/replay commands and notebooks. Fix identified defects and run the targeted regression tests they require. Do not expand this stage into a large statistical campaign or claim a performance advantage from smoke runs.

Finish docs/acceptance_report.md with exact commands, versions, test results, smoke-run paths, verified features, and genuine limitations. Update all affected module READMEs, root README, AGENTS.md, and STATUS.md.

Return a concise handoff containing: implementation summary; exact setup/build/test commands; the YAML fields the user should edit for physical-error-rate and decoder sweeps; commands for multiprocess simulation, isolated latency, analysis, and replay; output locations; and any unresolved issue. Do not state completion if a required decoder or circuit remains unavailable, a required test failed, or results were produced by a substitute implementation.
```
