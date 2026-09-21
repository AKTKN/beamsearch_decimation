# Codex Prompts: Migrate the Existing Package to the Search / Soft-BP / OSD-0 Hybrid

**Date:** 2026-09-21  
**Target repository:** https://github.com/AKTKN/beamsearch_decimation  
**Inspected main commit:** `a98279b5bca906a4c41c59f68c35b93d6996bbc2`.

## How to use these prompts

Make these two companion documents available in the Codex workspace:

1. `hybrid_search_soft_bp_osd0_specification.md` — normative algorithm, HSBP-ALG-1.0.
2. `hybrid_benchmark_data_and_hypothesis_specification.md` — experiment and data contract, HSBP-EXP-1.0.

Send the common instruction block together with Stage 1. Then send Stages 2 through 6 in order, after the preceding stage has completed its acceptance checks. The stages are separate implementation tasks, not six requests for plans. Keep one working branch across stages when practical. If starting a new Codex session, include the common block, the two specifications, and the current `STATUS.md`.

The algorithm specification is authoritative for decoding behavior. The experiment specification is authoritative for timing, labels, schemas, and scientific interpretation. These prompts prescribe how to migrate the existing implementation. If the checkout has advanced, inspect its actual state and adapt file locations without reverting unrelated changes. The inspected revision is a reference, not an instruction to reset the user's branch.

## Common instruction block

```text
You are implementing an authorized migration in the existing repository
https://github.com/AKTKN/beamsearch_decimation.

Use these supplied documents as implementation contracts:
- hybrid_search_soft_bp_osd0_specification.md (HSBP-ALG-1.0)
- hybrid_benchmark_data_and_hypothesis_specification.md (HSBP-EXP-1.0)

The new main decoder is:
bounded direct correction search -> finite soft-guided parallel min-sum BP ->
resume search and continue BP messages for a few cycles -> direct OSD-CS order 0.
Search starts before any BP run. Search state persists across cycles. BP retains
edge-message state within a shot; posterior LLRs are never reused as new priors.
The search, pattern selection, orchestration hot path, and diagnostics counters
must be implemented in C++. BP and OSD must use an explicitly patched, audited
opt-in interface in the existing ldpc dependency. Python orchestrates experiments.

This is a request to implement the current stage, compile it, test it, and update
documentation. Do not stop after producing a plan. Make reasonable implementation
choices where the contracts permit them. Do not invent missing scientific
parameters, silently change the algorithm, or claim benchmark improvements before
measuring them.

Read the root and relevant nested AGENTS.md files, STATUS.md, module documentation,
the dependency manifest, and the actual working tree before editing. My request
explicitly supersedes old instructions requiring cold-start sum-product BP,
hard fixation, static top-M screening, completing every K candidate, or no fallback
for the NEW profile. Update those instructions to distinguish the new profile
from the preserved historical screened_reference profile. This authorization
does not permit changing unrelated scientific/circuit contracts or historical data.

Preserve the old decoder, old BP-OSD-CS10 profile, and the existing published beam
decoder for reproducibility. Add an honestly named BP-OSD-CS0 baseline. Never
relabel CS10 data as CS0. The primary new hybrid fallback must be order zero.

Use the existing search_decimation environment and repository build conventions.
Keep the pinned dependencies unless a concrete incompatibility requires a
documented change. Work on a local topic branch when safe; preserve user changes.
Do not force-reset, overwrite old result directories, push, publish, or run large
production sweeps as part of these implementation stages. Bounded smoke tests,
clean-build tests, and the code changes requested here are authorized.

All comments, docstrings, public API documentation, error messages, Markdown,
notebook prose, and prompts committed to the project must be in English. Use
small cohesive modules, explicit ownership, typed Python APIs, validated shapes,
and docstrings describing arguments, results, mutation, units, and failure modes.
Do not create a second unrelated framework or rewrite working modules without need.

Keep the existing directories and responsibilities:
src, python_scripts, scripts, config, analysis, notebook, external_lib, assets,
tests, and any existing circuit/model artifact directories. Preserve spawn-based
multiprocessing, parent-only output writes, paired sampling, the canonical DEM
conversion, and exact circuit/observable mappings.

At each stage, add meaningful tests for newly introduced units, actually compile
and run the relevant tests, and fix failures before proceeding. Distinguish tests
you ran from tests only planned. Do not claim historical STATUS.md results as new
evidence. Update STATUS.md with changes, exact validation commands/results,
remaining work, and blockers. Maintain per-module README/Markdown explanations.

Ensure all authored ldpc sources, bindings, and build scripts are recoverable from
tracked patches or archives and are covered by dependency/source/build hashes.
The repository previously needed a fix for omitted ignored binding sources;
do not repeat that omission. Never bypass provenance checks to make a build pass.

At the end of each stage, give a concise report of implemented behavior, tests
actually run, important limitations, and the next stage's prerequisites. Do not
ask for confirmation of routine decisions already authorized above. If an actual
access/build limitation blocks completion, explain it precisely and preserve
reviewable work; do not mark the stage complete with an untested placeholder.
```

## Stage 1 — Reconcile contracts, configuration, and migration boundaries

```text
Implement Stage 1 of the hybrid decoder migration.

First inspect the actual checkout and read the two supplied specifications in
full. The reference checkout was main commit
a98279b5bca906a4c41c59f68c35b93d6996bbc2. At that revision:
- native/search.hpp implements static screening and cold hard-decimated BP;
- the opt-in ldpc.reference_bp interface implements the old flooding BP;
- decoder dispatch and implementation identity have hardcoded legacy cases;
- storage schemas and run/batch manifests are version 1;
- worker service timing records CPU and wall time, but native phases are wall-only;
- analysis/io.py rejects unsupported manifest versions;
- the BB circuit uses the existing qLDPC edge-coloring schedule.

Inspect at least AGENTS.md, STATUS.md, config.py, bp.py, native/, decoders/, runner/,
storage/, identity.py, provenance/, analysis/, CMakeLists.txt, dependency scripts,
external_lib/manifest.lock.json, and external_lib/patches/ldpc.patch. Use the
actual code to adapt this list if the repository has moved.

Create or update docs containing the two normative specifications. Add a brief
implementation map and decision log. Update AGENTS.md so the old algorithm's
restrictions apply to the historical profile and the new contract applies to
hybrid_search_soft_ms_osd0_v1. Preserve historical STATUS evidence as history.

Implement strict configuration models for the new decoder, with the search,
BP, finite-hint, OSD-only, numerical, budget, and profiling semantics in HSBP-ALG-1.0.
Resolve cycle-budget lists explicitly. Validate finite values, list lengths,
supported methods/schedules, resource caps, and order zero. Make the new kind
distinct from legacy decoder kinds. Prepare explicit profile identities for
the warm hybrid, search-plus-OSD ablation, and cold-BP ablation. Do not expose a
placeholder decoder as a functioning implementation before Stage 3.

Add an explicitly named upstream BP-min-sum/CS0 profile. Preserve the old CS10
profile and behavior. Ensure identity and dispatch logic are explicit and
exhaustive: a new kind must never fall through to the beam decoder by default.
All effective options must contribute to scientific/configuration identities.

Add tracked .yaml.example templates and integrate with the existing local-template
setup script without overwriting users' local configs. Preserve user-defined
physical-rate lists/sweeps; production configs must not silently choose rates.
Label small numeric smoke defaults as software checks, not tuned physics settings.

Define interfaces and ownership for a worker-owned immutable model, mutable
native search session, stateful ldpc min-sum session, OSD-only bridge, and compact
telemetry. Identify the exact files that need source/build hashes. Declare
new mutable sessions non-reentrant on the same object and reset between shots.

Tests required now:
- valid/invalid configuration parsing and resolved budget serialization;
- distinct CS0/CS10 identities and exhaustive decoder dispatch;
- unchanged parsing of existing legacy configs;
- template setup preserves local edits;
- no heavy numerical imports before the existing worker/thread bootstrap.

Run the relevant existing tests too. Update module docs and STATUS.md. Record
the remaining Stage 2-6 work explicitly; do not claim the hybrid is implemented
after configuration scaffolding alone.
```

## Stage 2 — Implement stateful min-sum and a true OSD-only bridge in the ldpc fork

```text
Implement Stage 2. Read the current STATUS.md and Stage 1 contracts first.

Extend the existing pinned ldpc checkout on an appropriate local topic branch
based on the repository's current opt-in patch. The inspected upstream pin is
d3429964cd4ffe1abfc041c6ec8b8425cb174f40. Preserve existing upstream APIs and the
old reference_bp interface. No hosted fork or remote push is needed to complete
this stage.

Implement an opt-in C++ stateful parallel min-sum session using ldpc's graph
infrastructure. Required operations: reset for a new syndrome, set/replace finite
channel fields, continue a bounded number of flooding iterations, expose hard
decision and final LLRs, and expose state snapshots only for focused tests.
The production hybrid must share this session directly in C++; do not copy its
edge arrays into Python between cycles.

Follow the exact HSBP-ALG-1.0 equations and arithmetic conventions:
- preserve immutable physical channel weights;
- keep check-to-variable and variable-to-check arrays;
- on a hint change retain check messages and recompute unclipped variable sums,
  clipped marginals, and extrinsic variable messages;
- never subtract from a clipped posterior to reconstruct an extrinsic message;
- all check updates consume the previous variable-message state before the
  variable pass begins;
- implement degree-zero/one checks, repeated minima, zero signs, clipping,
  finite parameters, and the specified hard-decision tie;
- accept at the hint-transition validity check or after a completed iteration;
- use the two-minimum check algorithm, reusable buffers, and no fast-math.

Finite hints use the specified signed_channel_magnitude_plus_margin rule.
Changing hints replaces the previous hint vector, including restoring unhinted
variables to their physical channel field. It does not accumulate hints or
reuse posterior LLRs as priors. Warm state is within a shot only.

Implement a direct native OSD-CS/order-0 bridge. At the inspected pin, order zero
invokes fast_solve without combination enumeration. Call the actual native OSD
kernel with the supplied LLRs. Do not use BpOsdDecoder.decode for this bridge:
that public wrapper runs BP first. Retain pinned signed-LLR ordering and its
tie behavior; do not substitute absolute LLRs or silently change tie rules.
Use original H and syndrome with all columns available and validate the result.
Prepare reusable objects outside per-shot timing, but retain per-shot sort and
elimination costs inside the OSD call. Make input/vector ownership safe.

Meaningful tests:
- independent small Python flooding-min-sum oracle, not a copy of the optimized
  implementation, compared iteration by iteration;
- tree and loopy cases, nonzero syndrome, clipping counterexample, repeated
  minima, zero messages, degree-one constraints, and empty/degenerate shapes;
- unchanged-hint continuation equals a concatenated run before any early exit;
- replaced/removed hints use retained messages correctly; new shots and
  exception recovery reset correctly;
- a valid correction can violate a finite hint;
- direct OSD output equals the pinned native kernel for the same supplied LLRs,
  including signed-order and tie fixtures;
- CS/order-0 and OSD-0 agree at identical inputs; no hidden BP call or higher-order
  candidate enumeration; rank-deficient/inconsistent inputs fail safely.

Compile the bindings and native tests incrementally. Include new headers,
binding sources, Python shims, and build scripts in the tracked fork patch or
archive. Update manifest/audit/runtime hashes and verify that patch restoration
recreates them. Do not bypass audit failures. Keep native thread count one by
default and release the GIL for native work.

Update external_lib and BP-module documentation plus STATUS.md with actual
commands/results and the API Stage 3 will consume.
```

## Stage 3 — Implement the bounded search and hybrid native decoder

```text
Implement Stage 3 against the tested Stage 2 interfaces.

Implement the new search and the complete per-shot state machine in C++17.
Retain the legacy screened decoder. Follow HSBP-ALG-1.0 exactly:

1. Begin with direct correction search and no initial BP run.
2. Nodes carry disjoint selected-one and forbidden-zero sets, residual syndrome,
   selected-one depth, physical cost, and a canonical pattern key.
3. U is the free neighborhood of the lowest-index active residual detector,
   ordered by physical weight, then canonical column index. Child k selects that element and forbids
   preceding elements, leaving later elements free.
4. Rank nodes by physical g plus the specified fractional residual-cover bound,
   then residual weight, then canonical pattern key. Do not use BP posteriors
   as physical weights or change the ranking formula.
5. Process children in the specified order and return the first generated valid
   correction. This is not a minimum-cost certificate.
6. Keep the frontier across cycles. Use one best unused generated, locally
   consistent pattern per BP attempt. Include its ones and zeros as finite
   hints; keep search restrictions separate from BP variables.
7. Warm-transition and run a small BP block, accepting if valid. Continue the
   same search/BP states when unsuccessful. No BP call per expanded search node.
8. Enforce global depth/node limits and per-cycle work budgets. Honor the
   precisely defined optional prefix CPU cap. Invoke direct OSD0 after the
   specified termination condition using last BP LLRs or clipped channel LLRs.
9. Validate every terminal correction using original H and predict through A.

Use distinct expansion and guidance queues or an equivalent tested structure.
Do not merge nodes by residual alone. Do not repeat already-used hints. Do not
restart search or BP at every cycle. Reset both for the next shot.

Implement a clear full-recomputation C++ reference path for tiny tests and an
efficient production path. Use immutable CSR/CSC, fixed edge IDs, compact node
arenas/parent deltas, reusable buffers, efficient residual XOR/popcount, and
well-localized hot metadata. Follow the Tesseract engineering adaptation rules
in the specification; these optimizations must preserve the finite-budget
algorithm's decisions. Avoid vector<bool> proxy access in random-access hot loops.

For incremental heuristic updates, include changed residual detectors, all
detectors adjacent to columns whose active counts changed, and detectors adjacent
to newly forbidden columns. Use the specified fixed summation order/tree in both
reference and optimized paths. Do not introduce epsilon heap comparators.
Only add early exits from minimum scans when the stated bound proves them safe.

Do not import detector penalties, at-most-two pruning, residual-only visited
pruning, beam truncation, or graph decomposition into the reference profile.
If an optimization needs different scientific behavior, defer it as a separately
identified experiment instead of silently adding it.

Implement cheap native summary counters and compact per-cycle/per-phase records
with both process CPU and wall durations. Do not serialize JSON in hot loops.
Expose a safe post-decode telemetry export operation for Stage 4. Record
terminal stages, zero-syndrome exits, cap reasons, hint identities, iterations,
expansions, OSD reach, and OSD LLR source. Avoid timing every node/edge.

Tests required:
- exhaustive small-matrix validation of branching, residuals, local rejection,
  and the heuristic lower bound against feasible completions;
- goal-on-generation order, depth-D goals, zero weights, empty syndrome,
  duplicate detector columns with different observable effects;
- persistent frontier, one-use hints, pool exhaustion, node caps and cycle caps;
- every terminal stage via deterministic fixtures, including zero-iteration BP
  acceptance and a forced OSD path;
- reference/optimized decision and counter equality under deterministic budgets;
- repeated use, concurrent independent instances, and exception reset;
- full correction validity and unchanged physical-cost computation;
- native Debug and release builds, ASan/UBSan where supported.

Use focused performance measurements on fixed synthetic fixtures to decide
whether added complexity reduces runtime. Report measurements as engineering
checks, not logical-error benchmark conclusions. Optimize measured bottlenecks
and stop optional tuning after the required paths are sufficiently verified.

Wire explicit decoder adapter/identity support and runtime source/build checks.
Update CMake, native tests, module docs, dependency hashes, and STATUS.md. The
new decoder should be callable by the end of this stage; full experiment-table
integration belongs to Stage 4.
```

## Stage 4 — Extend workers, timing, Parquet schemas, and atomic output

```text
Implement Stage 4 using HSBP-EXP-1.0 as the data contract.

Extend the existing runner rather than building a separate simulator. Preserve
physical circuit sampling, selected-sector projection, all BB observables,
paired decoder execution, spawn-based multiprocessing, and parent-only writes.
Each configured baseline must run on every same shot, including shots the
hybrid resolves early. Truth must never enter decoder selection or inference.

Retain the established outer process_time_ns/perf_counter_ns service boundary.
Add native process-CPU and wall timing for search slices, hint transitions,
BP iteration blocks, and OSD-only calls. Record the prefix aggregate and service
residual so prefix + OSD + service_other reconstructs outer service time.
Do not add overlapping prefix and child-phase durations as independent costs.
Use a compatible process CPU clock and record clock resolution/platform details.

Extract compact native event buffers after timed decoding and before the next
shot. Compute logical labels outside the timer. Keep heavy JSON/trace conversion,
Parquet writes, and analysis outside the timed decoder. Counters and phase-event
collection themselves remain measured work; do not subtract estimated logging
overhead. Provide profiling=none and profiling=phases, with honest null semantics.

Implement strict Arrow schemas and validators for:
- existing samples schema, retaining physical sampling identity;
- decodes/2 with terminal stage/reason, OSD reach, work counters, hints, phase
  durations, prefix/service residuals, and existing outcome fields;
- hybrid_rounds/1, one row per started cycle;
- decoder_phases/1, one row per actual phase call.

Follow the specification's exact meanings, nullability, units, and denominators.
An invalid BP hard decision has no logical-correction mismatch label. Empty
syndrome is a search exit with a separate reason and can still fail logically.
Distinguish OSD reach from OSD success. Record prefix/node-cap reasons explicitly.
Preserve physical code length separately from DEM mechanism count.

Update worker.py, pipeline.py, storage schemas/writer, identity, provenance, and
read interfaces end to end. Adding fields only to DecodeResult is insufficient.
Introduce run/batch manifest version 2 with explicit table versions and all
declared shards, row counts, and checksums. Commit each paired batch only after
all declared data are durable. Empty event tables must still satisfy the declared
policy. Keep version-1 reading support without rewriting historical artifacts.

Preserve timestamped run directories, immutable historical outputs, replay into
a new directory, and complete resolved JSON manifests. Include algorithm versions,
all decoder parameters/seeds, circuit/DEM/model hashes, exact dependency/patch/
source/build identities, CPU/compiler/libc/clock data, worker/thread settings,
decoder execution order, instrumentation mode, and schema versions.

Add deterministic integration tests for every stage and event path. Verify:
- phase sums, prefix residuals, counters, foreign keys, and terminal truth labels;
- paired sample/decoder completeness, including early hybrid exits;
- null versus zero durations and labels;
- v1 compatibility and v2 round trips;
- interrupted writes, missing/corrupted shards, and duplicated rows;
- no cross-shot BP state after warmup, failure, or replay;
- one-worker/multi-worker scientific output equality when time caps are off;
- new source/build hashes detect missing or modified authored files.

Run small end-to-end surface and BB smoke jobs with bounded shot counts, plus
an isolated one-worker latency smoke. Use the repository's existing authorized
smoke-rate conventions; do not launch a production sweep. Validate all 12 BB
observable labels. Document actual generated artifacts and test outcomes in
STATUS.md and the runner/storage/module docs.
```

## Stage 5 — Implement paired hypothesis analysis and reproducible notebooks

```text
Implement Stage 5 from saved artifacts using HSBP-EXP-1.0.

Extend analysis/io.py with manifest/schema version dispatch and validated access
to new tables. Keep historical v1 runs readable, with unavailable new fields
projected as null in memory. Do not invent historical stage information or mix
incompatible circuit, noise, model, timing, load, or decoder identities.

Create focused reusable analysis functions for terminal fractions, OSD reach,
phase costs, cycle-level rescue, stage-conditioned logical errors, unconditional
failure contributions, paired decoder outcomes, and paired timing differences.
All denominators and units must be explicit. Invalid decoding contributes to
block failure. BB block failure is per memory shot, not divided by 12 or rounds.

Implement the exact paired cost identity for each hybrid/baseline pair:
T_H - T_B = P + V - A*T_B + F*(O - T_B),
where F indicates OSD entry, A=1-F, P is measured native prefix duration,
O is measured OSD-only duration (zero when absent), and V is remaining service
time. Verify the identity per shot and in aggregates. Report all four terms,
including the fallback difference; never assume the guided fallback equals the
standalone baseline. Split avoided baseline cost by zero syndrome, nonzero search,
and guided-BP exits, and identify any pre-OSD decoding failures separately.

Implement paired accuracy differences and discordance counts. Preserve the
difference between validity/convergence and correct logical prediction. For
valid exits report conditional logical mismatch; for all shots report total
block failure and stage contributions. A low OSD reach fraction alone must not
be described as algorithmic success.

Provide Wilson rate intervals and reproducible paired bootstrap intervals for
mean CPU differences, cost terms, LER differences, time ratios, and optional
quantile differences. Include configurable batch-block bootstrap for correlated
timing observations. Track replay/trial identity so repeated timing measurements
of the same shots do not inflate independent LER sample size. A user-defined
accuracy margin may enable noninferiority reporting; if absent, report estimates
and uncertainty without declaring equivalence.

Update CLI scripts, shell wrappers, tracked YAML examples, report modules, and a
notebook that loads only saved Parquet/JSON artifacts. Provide these outputs:
- LER/block-failure curves with intervals;
- CPU and wall ECDF/survivor plots and mean/p50/p90/p95/p99 summaries;
- stage exit/reach curves, clearly separating zero syndrome;
- disjoint native phase costs and the paired cost-decomposition table/plot;
- stage-conditioned accuracy, unconditional contributions, and discordance;
- per-cycle search/BP rescue/work/cap statistics;
- ablation comparisons for warm versus cold BP and search without BP.
Only show extreme quantiles with appropriate sample/tail counts. Failed and
timed-out shots remain in runtime distributions. A prefix time cap is not a
hard real-time guarantee for OSD or for the full decoder.

Tests must use hand-checkable synthetic paired data with known answers,
including a case where the hybrid reduces OSD reach but is slower, and a case
where it is faster but less accurate. Test null/empty denominators, repeated
replays, incompatible groups, bootstrap reproducibility, and exact cost/error
accounting. Execute the notebook and report CLI on Stage 4 smoke artifacts.

Update analysis, notebook, script, config, and data-schema documentation and
STATUS.md. State clearly that smoke results validate the pipeline, not the
scientific hypothesis. Do not fabricate or overinterpret a performance advantage.
```

## Stage 6 — Clean restoration, final acceptance, documentation, and handoff

```text
Complete Stage 6 and the entire authorized migration.

Review HSBP-ALG-1.0 and HSBP-EXP-1.0 against the actual implementation. Resolve
remaining deviations, TODOs on required paths, schema mismatches, and stale
documentation. Preserve explicitly deferred optional experiments as deferred.
The core decoder, telemetry, paired analysis, and reproducible smoke workflows
must be working, not placeholders.

Perform a clean dependency-restoration/build check in an isolated temporary
checkout or build location that preserves the user's working files. Recreate
ldpc from the pinned upstream plus tracked patches/archives and ensure every
new binding/header/build source is present. Validate manifest, source, compiled
extension, and runtime hashes. Do not rely on untracked files left in ignored
external_lib checkouts. Preserve the repository's compatible pybind11/Stim build
conventions and avoid parallel Stim builds if they conflict.

Run the relevant full Python/native test suites, release build, Debug and
sanitizer checks where supported, legacy regression tests, and new native
reference-versus-optimized tests. Resolve concrete failures; do not repeatedly
broaden testing without a remaining risk. Keep exact commands and outcomes.

Run final bounded end-to-end acceptance workflows:
1. small circuit-level Z-memory surface run using the new hybrid, CS0 baseline,
   and at least one existing published beam profile;
2. small [[72,12,6]] BB run with R=6 and all 12 measured logical observables;
3. isolated one-worker latency run with phase profiling;
4. deterministic replay from saved samples into a new output directory;
5. multiprocessing run with scientific output equivalence to the same single-
   worker samples when clock-based stopping is disabled;
6. analysis CLI and notebook execution from the stored artifacts.

Supply example configurations for surface defaults d=5,7,9 and BB, configurable
rate lists/sweeps, all seeds/budgets/output locations, ablations, profiling, and
analysis settings. Production rate choices remain the user's responsibility;
do not execute an unrequested large sweep. Include optional CS10 comparison
configs without changing the new hybrid's OSD0 fallback.

Document the package in English with:
- algorithm equations and conventions linked to concrete APIs;
- state lifetimes, warm-message continuation, finite hints, and OSD-only calling;
- reproducible installation, clean build, validation, simulation, replay, and
  analysis commands;
- config reference and fully resolved manifest example;
- every table/field/unit/nullability and atomic commit/version policy;
- timing scope, phase overhead, CPU-versus-wall interpretation, and pairing;
- how to evaluate the four-term cost identity and stage-specific accuracy;
- historical v1/legacy-profile compatibility and migration behavior;
- actual limitations, deferred experiments, and known platform tie semantics.

Update README.md, AGENTS.md, STATUS.md, docs/, and per-module README/Markdown
files for every changed module directory, including external_lib, runner,
storage, analysis, scripts/config, and notebooks. Ensure function docstrings
describe arguments, returns, units, mutation/ownership, and errors where relevant.

In the final handoff, summarize implemented behavior and tests actually run,
point to example configs and exact commands for the user's next experiments,
and list any material limitations. Do not claim that the hybrid beats BP-OSD
or that its hypothesis is established by smoke tests. The completed package must
make that hypothesis directly measurable and falsifiable.
```

## Final review checklist for the human researcher

- The new path begins with search and runs no hidden preliminary or fallback BP pass.
- Search resumes its frontier; warm BP retains edge messages and replaces finite hints.
- Search patterns use the defined local U and canonical branch assignments.
- A first-valid result is reported without a minimum-cost or logical-correctness guarantee.
- The hybrid fallback is direct CS/order-zero on the specified LLRs.
- Every paired shot also has the declared baseline result and service time.
- Stage CPU/wall durations, OSD reach, logical labels, and fallback differences are stored.
- Historical profiles and data remain identifiable and readable.
- Native optimization preserves reference choices under finite deterministic budgets.
- The implementation has passed recorded tests and bounded real-circuit workflows.

These prompts intentionally separate algorithm correctness, systems performance,
and scientific evidence. Completion of the software work enables the comparison;
it does not predetermine its outcome.
