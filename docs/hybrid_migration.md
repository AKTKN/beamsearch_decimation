# Hybrid migration: preserved Stage 1 decisions

This file records the Stage 1 design boundary as history. Stages 2-3 now implement
the native APIs; [hybrid_native.md](hybrid_native.md) is the current implementation
reference and supersedes the planned paths/signatures and availability below.
Run/replay storage still requires Stage 4.

The normative contracts are [HSBP-ALG-1.0](hybrid_search_soft_bp_osd0_specification.md)
and [HSBP-EXP-1.0](hybrid_benchmark_data_and_hypothesis_specification.md). Their bytes
match the supplied workspace documents. The migration instructions are in
[the staged prompt](../prompts/codex_hybrid_decoder_migration_prompts.md).
Historical contracts and accepted evidence remain intact. Stage 1 supplies strict
configuration and the actual upstream CS0 baseline; it does not implement hybrid
search, stateful min-sum, direct OSD, new telemetry tables or paired hypothesis analysis.

## Configuration and decisions

`config.Hybrid` accepts the normative decoder fragment, including the distinct
`kind: hybrid_search_soft_bp_osd0`. Existing configurations continue to discriminate
on `profile` without requiring a new legacy `kind` field. Unknown keys and kinds
fail validation. All algorithm choices and normalized budgets enter decoder identity.
Name/enabled remain presentation/selection fields. Instrumentation uses the existing
`timing.profiling: none|phases`, enters the run/configuration identity and analysis
execution context, and does not change correction-algorithm identity.

| Profile | BP enabled | Warm messages | Availability after Stage 1 |
|---|---|---|---|
| hybrid_search_soft_ms_osd0_v1 | true | true | Configuration only |
| search_osd0_v1 | false | false | Configuration only |
| hybrid_search_soft_ms_osd0_cold_v1 | true | false | Configuration only |
| bposd_ms30_cs0 | Upstream | Upstream per-shot behavior | Callable, actual BP then CS0 |
| bposd_ms30_cs10 | Upstream | Upstream per-shot behavior | Preserved |
| screened_reference, beam8, beam32 | Historical | Historical | Preserved |

Ablation profiles supply their BP defaults; explicitly conflicting flags fail.
Search-only iteration budgets must be zero, preventing an ignored positive work
request. Kernel/finite-hint options remain serialized even for ablations where no
BP attempt runs. This conservative identity does not pool different configurations.
CS0 fixes order to zero. The historical CS10 class still permits its previous
explicit order and iteration overrides, preserving existing parsing and semantics;
its profile is not rewritten. Full effective parameters identify such variants.

Search scalar budgets broadcast to C immutable tuple entries; JSON contains lists.
BP budgets follow the same rule. Lists must have exactly C entries, including an
empty list for C=0. Scalars at C=0 resolve to empty lists. C=0 means direct OSD0
with the standard zero/inconsistent-syndrome checks, never standalone BP-OSD.
D=0 permits no expansion or guidance. Expansion counts may be zero; enabled BP
requires positive per-cycle iteration counts. Parameters are finite, scaling is
in (0,1], clip/margin are positive, and clipping is not artificially limited to
the old sum-product limit of 30. Unsupported hints, schedules, reductions and
nonzero fallback order fail. Prefix CPU budgets are optional positive signed-int64
nanoseconds; null disables clock-based stopping for deterministic replay.

Representability limits are explicit engineering limits: depth and each BP block
fit signed int32; node/expansion counts and total work fit uint64; C is at most
65,536 to bound configuration list allocation. The finite node cap includes the
root and must be at least one. These limits are not tuning recommendations.
Model-dependent graph/arena allocation sizes must additionally be checked at the
native boundary in Stages 2-3; representable settings do not promise available RAM.
The prefix cap is checked before expansion, child construction, transition and
full iteration; it does not cap an atomic operation or OSD/full-service latency.

`require_available_decoder` is import-light and exhaustive. The runner rejects an
enabled hybrid before numerical imports, output creation or circuit preparation;
implementation identity and adapter construction also reject it, including empty
models. Unknown kinds cannot fall through to beam. Disabled hybrid configs may be
kept alongside enabled available baselines. No placeholder kernel is registered.

The existing setup script discovers the new `.yaml.example` files automatically;
it never overwrites an existing file or symlink. Hybrid smoke/ablation templates
parse but are intentionally unavailable for execution until Stage 3. The production
template has empty rates and remains invalid until the user supplies a list or
sweep. Numeric smoke values are software checks, not tuned physics settings.
`bposd_cs0_smoke.yaml.example` is runnable now using existing v1 storage.

## Native interfaces and ownership reserved for Stages 2-3

These are implementation interfaces to build and test in later stages, not
callable Python stubs. Native public methods must document ownership/errors and
validate dimensions before mutation. Python handles only model preparation,
one-shot service calls, compact result conversion and subsequent event export.

| Component and intended location | Operations and ownership |
|---|---|
| `PreparedHybridModel`, project `native/hybrid_model.hpp` | Worker-owned immutable copied H(m,n), A(k,n), p(n), physical weights, flat CSR/CSC, canonical edge IDs and detector adjacency sorted by (w,index). Shared const ownership outlives every session; no caller buffer borrowed. Reject malformed/nonfinite models and checked-size overflow. |
| `SearchSession`, project `native/hybrid_search.hpp` | Own node arena, expansion/guidance heaps and used flags. `reset(s)`, `advance(expansion_budget, caps)`, `take_best_unused_hint()`. Preserve frontier across cycles; hint views are valid until next reset and never cross the Python hot path. No merging by residual alone. |
| `StatefulMinSumSession`, fork `src_cpp/stateful_min_sum.hpp` | Own s(m), fields/LLRs/accumulators(n), q/z(nnz), work buffers. `reset(s)`, `replace_fields(lambda)`, `advance(iteration_budget)`, `hard_decision()`, `llrs()`; test-only snapshots are owned copies. Retain z on hint replacement and derive q from unclipped sums. Production shares this C++ session directly. |
| `Osd0Bridge`, fork `src_cpp/osd0_bridge.hpp` | Own reusable pinned OSD/graph/probability storage; `decode(s, L)` with shapes (m,),(n,). Invoke pinned signed-LLR order-zero fast_solve without BP. Original columns remain available. Per-shot sort/elimination measured; returned correction is owned, original H validated. |
| `HybridDecoder`, project `native/hybrid.hpp` | Own search/BP/OSD sessions plus shared const model. `decode(s, settings)` resets first, runs search before BP, stops at first validity, and predicts A e. Release GIL for complete native call; one native thread. |
| Telemetry, project `native/hybrid_telemetry.hpp` | Owned scalar summary and bounded cycle/phase buffers. `export_telemetry()` produces owned copies after timed decode, before next reset; no JSON/truth in native loops. Arrays or borrowed views must not outlive the session's next decode. |

All mutable sessions are non-reentrant on the same object. Independent workers or
independent sessions may run concurrently. Reset between every shot, warmup and
exception recovery; warm messages never cross shots. Constructor/input errors
raise explicit exceptions; native numerical/allocation failures have explicit
failure reasons and cannot masquerade as exhausted budgets. Search patterns are
finite BP hints, never structural BP or OSD constraints.

Telemetry reserves exit stages `search`, `guided_bp`, `osd`, `failed`, reasons
`zero_syndrome`, `search_goal_generated`, `bp_transition_valid`, `bp_iteration_valid`,
`osd_valid`, `inconsistent_syndrome`, `osd_invalid`, `numerical_failure`,
`resource_failure`; fallback reasons `cycle_budget`, `frontier_and_hints_exhausted`,
`node_cap`, `prefix_cpu_cap`. Stage 3 will define these enums with counters and
records, and Stage 4 carries them through workers/storage. Durations use signed
int64 ns, counters uint64, missing events/labels null. `none` has null unmeasured
phase durations; `phases` has CPU/wall intervals per actual call and one cycle row
per started cycle. No synthetic event for an unentered phase. Prefix overlaps its
child phases; prefix + OSD + service_other reconstructs outer service time.

## Source/build audit and implementation map

No fork or native source/build bytes change in Stage 1. Existing dependency pins,
patches, reference binding and manifest hashes remain authoritative. The Python
adapter digest changes as expected, so newly produced decoder IDs differ from old
runs; historical run snapshots and IDs are never rewritten. Provenance now also
archives tracked `.yaml.example` and `.ipynb.example` files, even without local copies.

| Stage | Concrete files and obligations |
|---|---|
| 1 | `config.py`, `decoders/__init__.py`, `runner/pipeline.py`, `provenance/__init__.py`, `analysis/plots.py` CS0 labels, config templates, tests and docs. Budget serialization is consumed by unchanged `identity.decoder_identity` and `Config.resolved`. |
| 2 | Add fork `src_cpp/stateful_min_sum.hpp`, `src_cpp/osd0_bridge.hpp`, `src_python/ldpc/hybrid_bp/{bindings.cpp,__init__.py}`, `setup_hybrid.py`; adapt `bp.py` runtime verification. Preserve `reference_bp` and ordinary upstream APIs. |
| 3 | Add project `native/{hybrid_model,hybrid_search,hybrid_telemetry,hybrid}.hpp`; update `native/module.cpp`, `CMakeLists.txt`, adapter/identity verification and focused native tests. Make hybrid available only with tested real kernels. |
| 4 | Extend `runner/{worker,pipeline}.py`, `storage/{schema,__init__}.py`, provenance and replay. Introduce manifest/batch v2 and decodes/2, hybrid_rounds/1, decoder_phases/1; retain v1 readers. |
| 5 | Extend `analysis/{io,statistics,report,plots}.py` and focused paired-analysis module; update notebook and CLIs. Validate exact paired cost/error identities, bootstrap and denominators. |
| 6 | Clean restore/build, release/Debug/sanitizers, full legacy/native/integration suites, bounded surface/BB/replay/latency/analysis/notebook acceptance. |

For Stage 2, extend `python_scripts/audit_dependencies.py:PATHS`,
`python_scripts/build_dependencies.py`, `scripts/clean_build.sh`'s underlying
`python_scripts/clean_build.py`, and `external_lib/manifest.lock.json` plus
`external_lib/patches/ldpc.patch`. New aggregate build/runtime hashes must cover
all five new fork files above and transitive pinned headers used by the bridge:
`src_cpp/{bp,osd,sort,gf2sparse,gf2sparse_linalg,sparse_matrix_base,sparse_matrix_util,util,rng}.hpp`
(the actual include closure must be checked when implemented), as well as existing
reference sources/build script. The four new project headers, binding and CMake
must enter project compile/runtime hashes in Stage 3. Include authored ignored
`bindings.cpp` explicitly in patch export, source archives and pristine restoration
tests; never depend on untracked checkout leftovers. Keep pybind11 2.11.1 and
sequential Stim builds. Hash all additional implementation files if this map grows.

Inspection found a contract discrepancy: current v1 `valid_logical_mismatch` is a
non-null unconditional false on decoding failure; HSBP-EXP describes a nullable
label as the existing convention. Preserve the actual v1 bytes/schema/analysis;
implement the requested null convention in v2 and explicitly project legacy fields
when reading. Current native phase clocks are wall-only and overlap; no new CPU
or disjoint-phase claim is made in Stage 1. BB edge-coloring and all 12 observables,
physical sampling, undecomposed DEM and pairing remain unchanged.

Stage 2 prerequisites are now explicit: implement and independently test warm
min-sum and true OSD-only in the pinned fork, compile/audit/restore their sources,
and expose owned C++ APIs before the Stage 3 search/control path can use them.
