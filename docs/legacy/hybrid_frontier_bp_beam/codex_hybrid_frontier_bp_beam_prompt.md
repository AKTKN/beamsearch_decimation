# Codex implementation prompts: persistent search frontier and a BP state beam

This document is an implementation task, not a request for another design proposal. Use the common contract below in every stage, then run Stages 1–6 in order. In a single persistent Codex session, attach all three companion files at Stage 1 and send each numbered stage as the next prompt. If using a fresh session, provide the common contract, the companion files, and the current repository `STATUS.md` again.

Companion files:

- `hybrid_frontier_bp_beam_report.tex`: normative algorithm, mathematical definitions and control flow.
- `hybrid_frontier_bp_beam_parquet_schema.json`: normative typed dataset fields, keys, nullability and validation rules.
- `hybrid_frontier_bp_beam_example.yaml`: the user's physical grid and a concrete, unoptimized v2 starter configuration.

The TeX report is the algorithm source of truth. The JSON controls physical data representation; the YAML supplies starting values. If a genuine conflict is discovered, resolve it explicitly in the specification and tests before continuing. Do not invent an unrecorded optimization or silently reinterpret a budget. Paths below are repository-relative unless stated otherwise.

## Common contract — include with Stage 1

You are implementing HSBP-FB-2.0 in `https://github.com/AKTKN/beamsearch_decimation`. The development branch inspected when these instructions were written was `hybrid-decoder-stage1`, commit `f7128e94b746e3c8a2fa7923d5e2318195712f0a`. Inspect the actual checkout, branch, local modifications, `AGENTS.md`, and `STATUS.md`; do not reset the user's checkout to the inspected commit. Preserve existing changes and use an isolated implementation branch/worktree if needed.

Implement the work in the current stage completely, including focused compilation/tests and documentation. Do not stop at a proposed plan or an uncompiled patch. Do not run the production-sized example automatically. Finish with exact validation commands/results, changed modules, and remaining work for the next stage. Ordinary edits, builds and bounded tests are authorized; publishing, merging and a production experiment are not part of this task.

Preserve the existing package layout:

```text
src/             simulation modules and native C++ implementation
python_scripts/  executable Python entry points
scripts/         shell entry points invoking Python with explicit YAML files
config/          fully configurable experiment/decoder/output settings
analysis/        typed data loading, statistics and plotting
notebook/        notebooks using analysis modules
external_lib/    pinned dependencies and maintained fork patches
assets/          timestamped run output
tests/           Python/native/fork regression and integration tests
docs/            algorithm, configuration, build, data and migration documentation
simulation_data/ cached circuits, DEMs and prepared models, if already used
```

All code comments, docstrings, configuration comments, documentation and test descriptions must be English. Explain function arguments, return values, units, state ownership, invariants and failure modes. Favor small typed modules with explicit interfaces. Maintain root `AGENTS.md` and `STATUS.md`, and a README in every modified module folder. Preserve existing instructions in `AGENTS.md`; do not overwrite them with a generic replacement.

### Required behavioral change

The existing hybrid owns one BP session and replaces its hint with one newly selected pattern per cycle. The new decoder must have a persistent physical-cost search frontier `Q`, a separate pool `G` of never-admitted hints, and up to `W` retained candidate-specific BP message states. These are separate data structures with separate lifecycles. Do not implement a loop that overwrites a single BP state and call it a beam.

All search, heuristic evaluation, candidate scheduling, state management, BP control, solution selection and fallback control run in C++. Continue using the maintained `ldpc` fork for the BP kernel and direct OSD-only interface. Python coordinates model preparation, shared physical sampling, multiprocessing, typed output and analysis. Execute candidates sequentially on one native thread per worker. BP uses parallel/flooding message updates; that does not imply candidate-level CPU parallelism.

Preserve historical v1 profiles and output readers. Add a distinct adapter kind `hybrid_frontier_bp_beam_osd0`, profile `hybrid_frontier_bp_beam_ms_osd0_v2`, and algorithm version `HSBP-FB-2.0`. The width-one v2 profile is not a drop-in v1 equivalence claim.

### Algorithm invariants

1. Use the same selected-sector circuit-level model, original check matrix `H`, observable matrix `A`, syndrome `s` and immutable physical LLRs `w = log((1-p)/p)`. The numerical core accepts finite `0 < p <= 0.5`. Reuse the existing explicit removal of zero-probability DEM variables, persisting the column/observable maps; reject unsupported inputs. Do not merge equal detector columns with different observable effects. Never pass sampled truth into the decoder.
2. A search node is a partial assignment `(F0,F1)` with zero-completion `ebar`, residual `r=s XOR H*ebar`, ones-depth `|F1|`, and cost `g=sum(w[F1])`. Branch on the lowest-index active residual detector. Its free incident variables, including degrees one and two, are sorted by `(physical_weight,index)`. Child `j_l` sets all earlier variables in that ordered list to zero and `j_l` to one. Later neighbors remain free. Follow the report exactly.
3. Search ordering is `(g+h, residual_weight, canonical_pattern, node_id)` with the report's fractional-cover heuristic. Use physical weights, binary64, the specified fixed reduction tree, and no fast-math. The required version does not perform incumbent cost-bound pruning. No residual-only deduplication or BP-posterior substitution for the physical heuristic.
4. The optional detector beam limits a search residual excursion from the running minimum. It is neither a beam width nor a branch depth. The starter disables it. Search depth and hint depth are independent. Generated-node counts include the root and infeasible children. A node or expansion cap freezes further generation; existing guidance and BP states can continue.
5. BP fields are finite `lambda_i=(1-2*b_i)*(w_i+margin)` on the entire hinted pattern and `w_i` elsewhere. Replace the full field, do not add hints repeatedly. `hint_mode=none` explicitly restores physical fields. Raw fields are not prematurely clipped. Original `H/s` and all edges remain in use.
6. BP is flooding min-sum with check syndrome sign, configurable positive scaling <=1, finite clip, sign(0)=+1 and hard-decision LLR tie -> one. Degree-one checks send signed clip without the scaling factor. Extrinsic subtraction uses the unclipped variable sum. Check validity after a field transition and after every complete iteration.
7. Freeze the retained BP beam at cycle entry. New candidates inherit only from the deepest strict ancestor available in that frozen beam; otherwise initialize cold. Continuing candidates use their own state. Same-cycle updated/new states and unrelated siblings cannot be donors. Clone messages, not just posterior LLRs; posterior beliefs never become new channel priors. Cold ablation also resets continuing candidates.
8. Select up to `A_c <= W` fresh proposals from `G`, combine them with retained candidates, and allocate a **pooled** `B_c` iteration budget, capped globally by `T_max`. Sort tentative candidates by node ID, rotate by `cycle_index % pool_size`, then assign one token per pass up to per-visit cap `J`. Evaluate in the same order. Positive-quota admission removes a new node from `G` immediately before initialization; zero-quota proposals remain in `G`. Unused tokens are not redistributed or carried.
9. Rank unresolved usable states by `(BP_residual_weight, physical_search_f, node_id)`, retaining at most `W`. The `physical_only` ablation uses `(f,node_id)`. A BP eviction never deletes the node from `Q`. An evicted BP node is not readmitted as that same candidate. Descendants remain eligible.
10. Every syndrome-valid correction is submitted globally, even when soft BP violates its hint. Record hint disagreement and do not claim that such a result solves the restricted branch. Compare complete corrections by `(physical_cost, full_correction_bits_lexicographically)`. Never score by truth or logical outcome.
11. Default stopping is `first_valid`. `bounded_improve` continues for at most `K` cycles counting the first-discovery cycle as cycle one, within all original caps. Maintain distinct first-solution source, final winner source and prefix stop reason. Solved BP candidates retire. If any incumbent exists, return it without OSD.
12. Otherwise call direct OSD-CS0 once on original `H/s`, with the best retained candidate's signed clipped LLRs or clipped physical channel if none remains. Preserve pinned `ldpc` signed-LLR ordering and tie behavior; no absolute-value substitution. No hidden BP pass. Implement the named channel-only and field-release handoff diagnostics exactly as specified.

The example retains the user's surface `d=5,7`, BB72 distance 6, `R=d`, rates `[0.002,0.003,0.005]`, 30,000 shots per point, eight workers, and seeds. Its new defaults are `W=2`, eight cycles, eight expansions per cycle, 64 global expansions, 4096 generated nodes, 20 pooled BP iterations per cycle and 160 globally, no small search-depth limit, hint depth 10, and CS0 fallback. These are not optimized or proven superior to beam8. Width comparisons must retain the same pooled iteration and search limits; record clone/transition cost separately.

## Stage 1 — Repository audit, contracts and strict configuration

Read the common contract and all companion files. Inspect the current implementation before editing. In the inspected checkout, useful starting locations were:

```text
src/qec_bp_benchmark/native/hybrid.hpp
src/qec_bp_benchmark/native/                 search, bindings and adapter interfaces
src/qec_bp_benchmark/config.py
src/qec_bp_benchmark/storage/schema.py
src/qec_bp_benchmark/storage/telemetry.py
analysis/quick_plots.py
external_lib/patches/ldpc.patch
```

Locate actual sampling, worker, build, dependency-lock and baseline modules; do not invent paths based on these examples. Record a concise implementation map and the actual source/dependency hashes in `docs/hsbp_fb_v2_migration.md`.

Audit the current native hybrid: one BP session, hint replacement, work counters, queue semantics, CS0 bridge and timing boundaries. Audit the `ldpc` opt-in stateful min-sum API: snapshot fields, field replacement, reset and iteration semantics. The inspected fork had `snapshot()` but lacked the complete validated restore/clone interface required here. Extend this opt-in API while preserving baseline BP/BP-OSD behavior. The inspected upstream `ldpc` base was `d3429964cd4ffe1abfc041c6ec8b8425cb174f40`; confirm the actual lock and save any differences.

Add strict immutable configuration models for the new adapter/version and typed-output settings. Reject unknown keys, NaNs, invalid enums and incompatible combinations. Expand scalar cycle budgets to arrays of exactly `max_cycles` entries and save the expansion. `max_cycles=0` is a valid direct-CS0 diagnostic; then all cycle arrays are empty and total BP work is zero. Finite depths and detector beam are nonnegative, while `null` has the explicit meanings in the report. `max_generated_nodes>=1`; all counters must fit the native types without truncation.

Validate at least:

- `0 <= admissions_per_cycle[c] <= beam_width`; every pooled/global/visit budget is a nonnegative integer. `J=0` means no BP work; do not enter a nonterminating allocation loop.
- BP enabled requires `beam_width>=1`; BP disabled requires width zero, admissions zero and all BP iteration budgets zero.
- `max_total_iterations` caps actual work even if the sum of cycle budgets is greater. Both configurations are valid and must have documented behavior.
- `max_depth=null` is different from zero; `hint_max_depth` may be null or a nonnegative integer.
- `state_inheritance` accepts `retained_ancestor` or `cold`; `retention_score` accepts `residual_then_physical` or `physical_only`.
- `hint_mode` accepts `soft` or `none`. Margin remains finite and positive in the default soft policy; do not misrepresent zero margin as no hint.
- `stopping.mode` accepts `first_valid` or `bounded_improve`; `post_solution_cycles>=1`, ignored under first-valid but still persisted.
- Only direct `OSD_CS`, order zero, supported LLR-source enums and pinned ordering are accepted for v2.
- Native threads equal one; numerical and reduction semantics match the report.
- Mandatory typed summary/candidate/solution datasets cannot be silently disabled. Detailed search-node tracing, phase timing, compression and buffer sizes are explicit settings. Raw message/per-iteration trace remains disabled for production.

Preserve legacy configuration parsing through separate versioned models. Do not reinterpret the old `iterations_per_cycle` as a pooled budget or silently route a v1 profile to v2. The supplied YAML contains new fields and is not a claim that the unmodified parser accepts it.

Copy the three specification files into a suitable `docs/`/`config/` location, retaining a source-of-truth link. Create a **separate** tiny smoke config with surface distance 3, BB72 distance 6, one physical rate, a few dozen shots, and bounded work. Keep the production-sized example unchanged. Unit-test valid/invalid configurations and budget resolution, run the current relevant baseline tests, and document the stage result in `STATUS.md`.

Acceptance: strict v2 configuration parses; legacy profiles still parse identically; package imports/build bootstrap work; the exact remaining native API work is documented.

## Stage 2 — Persistent native search and deterministic reference oracle

Implement the v2 search in C++ as a reusable stateful component with immutable graph data and shot-local state. Reuse low-level primitives where safe but keep v1 behavior stable.

Implement canonical partial assignments, parent links/deltas, monotonically increasing node IDs, canonical zero-prefix children, original residual bitsets, the report's heuristic and exact total ordering. Maintain independent `Q` and `G` membership with explicit state flags. Roots, terminal nodes and infeasible nodes are never BP guidance. Once admitted, a node cannot re-enter `G`. The guidance pool must remain available after an expansion/node cap freezes generation.

Specify and test every counting boundary: root construction, eligible-parent expansion start, child construction, local infeasibility, terminal generation/pop, stale pop, finite depth, detector-beam discard and truncation halfway through a parent. If immediate first-valid stopping occurs inside a child loop, count only constructed children and record remaining siblings as ungenerated. Reaching a numeric cap exactly is not a cap-hit until it actually blocks requested work; use this same interpretation in summary fields and tests.

For `on_pop`, generated terminal nodes are queued but never placed in guidance. Permit terminal/stale/cutoff pops at the head of `Q` while processing a search slice even when the expansion allowance is zero; do not skip a higher-priority eligible nonterminal merely to reach a terminal deeper in the queue. Once the head is an expandable nonterminal and no expansion allowance remains, stop the slice. A global node/expansion cap freezes child generation but does not suppress valid terminal pops already at the queue head. Document these rules consistently in the report and tests.

Avoid rescanning immutable structures unnecessarily: canonical CSR/CSC, static neighbor ordering, contiguous arenas, reusable scratch bitsets and parent-delta pattern representation. Implement the exact recomputing heuristic as a reference path first. An incremental implementation must update the entire dependency closure affected by changed active detectors and free-variable counts; it must produce the same scores under the fixed reduction tree. Keep both kernels for differential tests. Do not introduce stale priorities, unproved residual deduplication or a different heuristic under the label of optimization.

Implement a tiny independent enumerating reference over GF(2). Test:

- The children partition all feasible extensions according to their first selected incident free variable.
- Lower-bound inequality against exhaustive compatible completions on random tiny partial assignments.
- Degree-one and degree-two variables, zero-cost weights, zero residual, no free neighbor, identical detector effects with different observable effects, and forbidden zero-prefix variables.
- Root-included node limits, depth zero/null/finite, expansion zero, on-generation versus on-pop, empty frontier, detector-beam semantics and mid-parent truncation.
- Exact native/reference node selection, physical score, residual and counter agreement on deterministic fixtures.

Design a thin internal solution-submission interface for Stage 4 without adding sampled truth to it. Provide bounded search slice and queue/guidance inspection interfaces for Stage 3. Compile and run native tests before moving on. Update module README and `STATUS.md` with supported/remaining functionality.

## Stage 3 — Forked BP state restoration, inheritance and beam scheduling

Implement safe native BP snapshot/restore/clone operations in the maintained `ldpc` fork or its existing opt-in extension. Update the reproducible fork patch and build identity. A snapshot must represent raw fields, check and variable messages, unclipped sums, clipped posterior LLRs, hard decisions, and lineage iteration count. Validate model/weight/syndrome/shot/numeric-format compatibility. The graph remains shared immutable data; mutable message buffers cannot alias across candidates.

Verify the flooding min-sum equations against a separate reference implementation. Include zero-message sign, degree-one checks, scaling, clipping, exact-zero hard ties and the difference between `S-z` and `clip(S)-z`. All new check messages must be derived from the previous iteration's variable messages. Restoring a snapshot and replacing a hint keeps check messages and recomputes fields/sums/posteriors/extrinsic messages; copying only marginals is insufficient.

Implement the retained state beam and scheduler entirely in C++:

1. At cycle entry, freeze the previous retained beam as donor snapshots. Use at most `W` frozen states. No full-state archive per generated node.
2. After search, propose up to `A_c` fresh nodes from `G` by `K_S`; combine with continuations and reject duplicate node IDs.
3. Compute `T_c=min(B_c,T_max-used)`. When disabled, `T_c=0`, `J=0`, or the pool is empty, skip transitions safely. Zero-work conditions do not consume admissions.
4. Apply the rotated round-robin allocation exactly, then evaluate sequentially in that order. New zero-quota proposals stay in `G`; continuing zero-quota candidates retain their previous state.
5. For each actually started new visit, record admission and select the deepest available strict ancestor in the frozen entry beam. Otherwise use a cold seed. Continuations use their own state, except under the explicit cold ablation. Freeze donor eligibility for the whole cycle.
6. Check transition validity, perform at most the allocated full iterations, and submit a valid result immediately through the central solution interface. Do not redistribute unused tokens.
7. Reconcile usable unresolved evaluated/carried states, rank by the configured key, and retain at most `W`. Update keep/evict/retire decisions and membership rows even for partial terminal cycles. Search membership is independent.

Logical work counters count only newly executed iterations. Copied lineage counters must never inflate the global budget. Record actual clone counts/bytes and live-state peak. Required working memory is at most `3W` full states with straightforward frozen donor + continuation + new-candidate buffers. Reuse or move buffers where it preserves snapshot semantics; no aliasing shortcut.

Implement tests for nearest available ancestor rather than immediate-parent assumptions; no retained ancestor; unrelated siblings; donors created during the same cycle; own continuation; cold reset; field replacement removing obsolete hints; cross-shot reset; wrong-model/shot restore rejection; and caller-owned snapshot lifetime. Run an address/undefined-behavior sanitizer target for ownership-sensitive native tests when available.

Hand-check quotas for `W=A=2`, `B=20`, `J=20`: first cycle with two new candidates gets 10 each; a later four-state tentative pool gets 5 each. Test unequal budgets, `J=0`, zero quotas, integer remainders with rotation, early success with unused tokens, global budget exhaustion, and eviction without Q removal. Assert no more than 160 actual BP iterations under the example regardless of width.

Acceptance: candidate-specific states and scheduling pass native/reference tests; v1 and baseline regression outputs remain unchanged; fork rebuild is reproducible; Stage 4 can consume a clear native result/event interface.

## Stage 4 — Integrated decoder, solution policy and direct CS0 fallback

Wire the persistent search and BP beam into a new native controller and Python adapter. There is no hidden initial BP block. The zero-syndrome shortcut returns a verified zero correction without constructing a root or running a cycle, and emits a zero-syndrome solution event.

Define a single deterministic solution-submission path. Validate on original `H/s`, compute physical cost in canonical variable order, compute predicted observables without truth, and update the incumbent by `(cost,bitvector)`. Keep all valid discovery events, including duplicate corrections. Record candidate hint disagreements; a soft result violating a hint is globally usable but never proves that branch solved. Remove solved candidates from BP retention while leaving search lifecycle independent.

Implement both stop policies. For first-valid, exit on the first deterministic valid event. For bounded-improve, the first-discovery cycle counts as one of `K` allowed cycles; all original generation, expansion, BP and CPU limits remain active. A terminal partial cycle must reconcile the most recent complete states and record unprocessed retained candidates as carried. No partially computed BP iteration may become a donor or fallback state.

Make the no-remaining-work predicate consider **future** cycle budgets, live Q/G, retained BP states, global remaining limits, hint depth, and whether any candidate can receive a positive quota. A zero budget in the current cycle alone does not mean exhaustion if a later cycle can do work. Queue exhaustion alone does not end usable BP work. A generation cap is not a global immediate fallback trigger. Record prefix stop reason independently of the eventual solution source.

An optional prefix process-CPU cap is checked before expansions, child construction, BP transitions and full iterations. Atomic work can overshoot; record the overshoot rather than claiming a hard deadline. OSD is outside this cap. All work limits apply in both stopping modes.

If no incumbent exists, select the best retained usable state by `K_B` and call the native OSD-only bridge with its signed clipped LLRs; otherwise use clipped channel. Implement `channel_only` and `best_retained_release` diagnostic handoffs, preserving their provenance. The latter replaces fields by the physical channel while retaining check messages and recomputing variable state; no extra BP iterations and no claim of exact de-biasing.

Require CS0 on original H/s and preserve the pinned signed-LLR ordering. Test that the bridge does not rerun BP or enforce hint variables as hard constraints. Preserve numerical/model/resource errors as explicit statuses. Normal nonconvergence can invoke OSD; invalid models or unsafe numerical state must not be hidden as an ordinary successful fallback.

Add integration fixtures covering:

- Search success before BP; transition success with zero actual iterations; BP iteration success; no prefix success followed by valid CS0; explicit invalid/error handling.
- A valid soft completion that violates its hint.
- Duplicate discoveries, equal-cost lexicographic ties and first-discovery/winning-source differences in bounded-improve mode.
- First-valid and bounded-improve at exact cycle boundaries; zero cycles; CPU cap before/after atomic work; caps with guidance still usable.
- Empty final beam, best retained fallback, released fields, channel-only fallback, and direct CS0-only baseline fixture.
- Repeatability on identical input and no state leakage across successive shots in a reused worker.

Add the new decoder registry entry and CLI dry-run/config validation. Run a bounded native/Python integration smoke test, with telemetry export still in memory if Stage 5 storage is not yet wired. Update `STATUS.md` and module documentation.

## Stage 5 — Separate typed Parquet datasets, reliable execution and analysis

Implement the companion JSON as explicit PyArrow schemas and cross-table validators. This new output layout must use separate dataset directories by data type, not one wide shot table or JSON event arrays embedded in a row:

| Dataset | Grain |
|---|---|
| `conditions` | One per physical condition |
| `decoder_profiles` | One per resolved decoder identity |
| `shot_inputs` | One per sampled physical shot, shared across decoders |
| `decode_results` | One per decoder invocation |
| `search_summary` | One per v2 invocation |
| `bp_summary` | One per v2 invocation |
| `cycles` | One per started v2 cycle |
| `patterns` | One per admitted BP node |
| `bp_updates` | One per actually started candidate visit |
| `bp_beam_membership` | One per retained candidate after each cycle |
| `solution_events` | One per valid discovery, including duplicates |
| `osd_calls` | One per actual direct fallback call |
| `phase_timings` | Exclusive phase/context aggregates when profiling |
| `search_nodes` | Optional debug trace of constructed nodes |

Use `(run_id,condition_id,shot_id)` as the physical shot key and add `decoder_id` for a decode key. Per-decode node, update and event IDs are local and deterministic. Use explicit uint64 counters/IDs, uint32 indices, int64 nanoseconds, finite float64 scores, UTF-8 metadata and packed binary vectors as declared in JSON. No schema inference. Enforce bit lengths and zero padding. Infeasible debug scores are null with a status, never NaN/Infinity.

Store the sampled syndrome and true logical observables once in `shot_inputs`. Give every decoder the same syndrome. Decode-service APIs must not accept truth. After the service timer, derive truth labels for every valid `solution_events` correction separately. **Do not copy the final winner's prediction or failure label into all earlier events.** This is a material difference from the previous single-terminal-event telemetry path.

Every v2 invocation, including zero syndrome, has summary rows with real zero counters for unexecuted work. Baseline/legacy adapters have normalized results and available faithful terminal attribution; do not fabricate v2 candidate rows or unavailable counters. Extend baseline adapters to expose their returned fault correction where required for explicit syndrome verification. If the pinned interface cannot provide it, document the limitation and an explicit schema/API resolution rather than claim verification of an unobserved correction.

Implement worker-owned buffers and batch shards. Never append from multiple workers to the same Parquet file. Write bounded temporary shards, close/validate/hash them, atomically rename, and commit a batch inventory only once all required dataset shards are ready. Analysis must read committed inventory entries. Persist empty dataset schemas and zero counts in the inventory without requiring empty files. Record row counts, key ranges, schema IDs and hashes. Interrupted batches are not counted as completed; resume is idempotent and validates exact identities.

The timestamped run directory contains fully resolved config and provenance JSON plus model artifacts. Save circuit/DEM/sector/column/observable maps, normalization details, sampler version and deterministic seed/chunk policy, dependency source/fork patch hashes, compiler/flags/binary hashes, thread limits, CPU context, telemetry settings and decoder execution ordering. IDs must be independent of worker completion order. One versus two workers must produce identical physical inputs/decoder outputs under fixed work limits, although timing values will differ.

Measure service CPU/wall consistently for all decoders, including required conversions, prediction and final verification. Exclude sampling, detailed Python telemetry conversion, offline truth labels and Parquet writing. Native in-memory recording remains part of service cost. Use exclusive phase scopes with suspended parent clocks or equivalent accounting. Record clone/field/iteration/rank/search/solution/OSD costs and adapter remainder without double counting. Profiling-off records counters and candidate histories but null unavailable phase durations; it must preserve deterministic algorithm results. Keep raw messages and per-iteration events disabled by default.

Update `analysis` with inventory-aware joins and diagnostics. Provide a notebook using these modules rather than embedding simulation logic. Include:

- Block failure rate with uncertainty by condition/decoder; invalid decoding and valid logical mismatches separately. BB72 failure is any of 12 tracked observables, not divided by 12 or by rounds.
- Paired discordance counts and paired physical-shot bootstrap differences between v2, v1, beam8 and BP-OSD-CS10; resample physical shots, not candidate events.
- CPU/wall ECDF and survival plots; mean, median, p90, p99 and p99.9 with sample counts and uncertainty/insufficient-tail-data flags.
- First-solution rates, winning-source rates and OSD reach rates as distinct quantities. Stage-conditional failure is descriptive selection, not a causal estimate.
- Search, BP preparation/clone, BP iteration, ranking and OSD CPU contributions; checks that phase sums match service time.
- Admissions, iterations, queue sizes, retained beam sizes, donor availability, cold fraction, clone bytes and hint disagreement versus success/failure and latency.
- Whether extra candidate states improve accuracy at fixed pooled work; whether ancestor inheritance is actually occurring often enough to matter.
- A speed–accuracy frontier and paired time difference versus beam8; no claimed advantage from unmatched noise/circuit/round/timing configurations.

Add typed round-trip, key/foreign-key, padding/null, counter-event consistency, per-event label and time-accounting tests. Test empty datasets, missing shards, duplicate-key rejection and simulated crash/resume. Preserve historical readers and old notebooks. Update module READMEs and `docs/data_dictionary.md`, `docs/run_manifest.md`, and the migration guide.

## Stage 6 — Verification, controlled variants and reproducible handoff

Run all required focused native/fork/storage tests and the relevant baseline regression gates. Run a bounded end-to-end smoke experiment for both rotated surface and BB72 under circuit-level noise. Reproduce a small fixed-input batch with one and two spawn workers and compare non-timing outputs. Run the accounting/manifest validator and generate the notebook's core figures from smoke data; label them as validation, not scientific performance evidence.

Audit the pinned beam baseline before interpreting relative accuracy. The inspected public source at `084a475b05fb64308103317a1ce5a0c4b0be58aa` excluded candidate variables of degree <=2, and its no-eligible-variable handling requires inspection. Record actual compiled source identity and model column-degree histograms. Preserve the existing beam8 profile for historical comparison. If correcting candidate eligibility/no-candidate behavior, implement a separately named audited profile, add fixtures proving safe termination and no repeated fixation, and report the difference explicitly. Do not silently improve or degrade the baseline used in previous runs.

Create separately named YAML variants and dry-run validation commands for:

1. v1 high-budget, v2 width 1/2/4 with identical search and pooled BP budgets, beam8 and BP-OSD-CS10.
2. Residual-first versus physical-only BP retention; ancestor inheritance versus cold; soft hints versus no hints.
3. Search-plus-CS0 with BP disabled, and actual unbiased BP-plus-CS0 as a separate existing/native baseline. Search budget zero does not magically add unbiased BP.
4. Detector beam off versus 15; first-valid versus bounded-improve with K=2.
5. Guided, channel-only and field-release OSD handoffs.

Do not run the full combinatorial grid automatically. Generate a small ordered experiment plan, starting with architecture/width comparisons and using independent or held-out validation for tuning. Add a separate one-worker isolated-latency configuration; throughput timing with eight concurrent workers does not establish a real-time tail-latency claim.

Ensure the root `AGENTS.md` and `STATUS.md` describe actual implementation status. Every modified module folder has an English README. Complete documentation for building the fork/native code, configuration fields/units, algorithm/ownership/stopping, output tables and keys, timing, failure semantics, resume, historical migration, and bounded smoke reproduction. Public APIs have argument/return/ownership documentation and useful internal comments.

Provide an implementation handoff with:

- The new profile name and supported CLI/shell commands, including config dry-run, build, focused tests, smoke run, validation, analysis and notebook generation.
- Exact source/dependency hashes, build identity and tests actually executed, including any gate that could not run and why.
- A compact list of the behavioral changes from v1 and baseline compatibility evidence.
- Location of the saved smoke run and its committed inventory, plus schema/data documentation.
- Remaining limitations and a prioritized production experiment sequence; no unsupported claim that the new decoder beats beam8.

Completion means a fresh environment can build, run the bounded smoke benchmark, validate all typed datasets and reproduce the analysis using only committed code/configuration and saved provenance. Finish the implementation rather than returning another implementation prompt.
