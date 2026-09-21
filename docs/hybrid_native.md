# Hybrid native implementation — Stages 2 and 3

The implementation follows [HSBP-ALG-1.0](hybrid_search_soft_bp_osd0_specification.md).
[HSBP-EXP-1.0](hybrid_benchmark_data_and_hypothesis_specification.md) defines the
experiment integration, now implemented by Stages 4–5 in [hybrid_data.md](hybrid_data.md).
The hybrid and its two ablations are callable through `DecoderAdapter` and the
paired runner, with complete v2 telemetry tables.
Historical screened, CS10, CS0 and published beam interfaces remain available.

## Public services and ownership

```python
from qec_bp_benchmark.config import Hybrid
from qec_bp_benchmark.decoders import DecoderAdapter

# problem is an existing canonical DetectorProblem with immutable H, A and priors.
decoder = DecoderAdapter(problem, Hybrid(), profiling=True)
result = decoder.decode(syndrome)       # binary (m,), no truth argument
summary = result.hybrid_summary         # owned scalar dictionary
telemetry = decoder.export_telemetry()  # after timed decode, before the next shot
```

The complete adapter service includes input copying, native reset/search/BP/OSD,
full original-H validation, A prediction and physical cost. `correction` has shape
(n,), prediction has shape (k,), and both are null on failure. Here n is DEM
mechanism count, never physical code length. Prediction preserves all BB observables.
`status`, `native_status` and `hybrid_summary` distinguish algebraic validity,
terminal stage and reason; they make no claim of logical correctness. Truth-based
labels belong to the evaluator and do not enter native decoding.

`Hybrid(profile='search_osd0_v1')` disables BP attempts and uses channel LLRs at OSD.
`Hybrid(profile='hybrid_search_soft_ms_osd0_cold_v1')` resets messages at each hint.
Both keep search persistent and have distinct identities. Per-node diagnostic
traces are unsupported and `diagnostics=True` is rejected for hybrid adapters;
use phase profiling and post-decode event export. Legacy diagnostics are unchanged.
`profiling=False` retains counters but returns null native phase times and empty
event lists. Event export copies owned dictionaries/lists; later calls cannot
mutate previously exported telemetry. Sessions are not reentrant on one object.
Independent native decoder objects can run concurrently with the GIL released.

Native invalid inputs raise `invalid_argument` (Python ValueError), and concurrent
use raises `logic_error` (RuntimeError). Per-shot allocation/size and nonfinite
arithmetic failures become `failed/resource_failure` or `failed/numerical_failure`.
Input validation failures propagate rather than becoming budget exhaustion.
Every new native decode clears search/telemetry and logically invalidates old BP
state; physical BP clearing is deferred until the first attempt. Search-only
successes therefore avoid touching edge arrays. Subsequent shots, including after
warmup or failure, cannot reuse previous-shot messages.

## Fork API

`bp.verified_hybrid_backend()` loads only the intended opt-in `ldpc.hybrid_bp`
extension and verifies its upstream pin and aggregate source/build digest.
Its Python types are documented in the tracked fork patch's `__init__.pyi`.

| Operation | Shapes, mutation and behavior |
|---|---|
| `StatefulMinSumSession(rows,n,probabilities,llr_clip=25,scaling_factor=1)` | Copies sorted unique row indices and p(n) in (0,0.5]; graph and priors are owned; parameters must be finite. |
| `reset(syndrome)` | Binary s(m); invalidates previous state before validation, clears q/z and iteration count; no BP iteration. |
| `replace_fields(fields)` | Finite fields(n), replaces the entire channel vector, retains check messages z, recomputes unclipped S, clipped L and extrinsic q, then tests original syndrome. Returns validity. |
| `replace_hint(pattern,margin)` | Sorted unique (column,bit) pairs; builds fields from immutable physical weights and signed magnitude plus positive finite margin. Removed hints restore physical fields. Returns transition validity. |
| `advance(iterations)` | Nonnegative integer; stops on validity, returns completed full iterations and validity. Uses previous q for the whole check pass, then the variable pass. |
| `snapshot()` | Owned copies of fields/S/L(n), q/z(nnz), decision(n), completed count. Requires active fields; intended for focused tests. |
| `Osd0Bridge(rows,n,probabilities).decode(s,L)` | s(m), finite L(n). Calls actual pinned `OsdDecoder::decode`, COMBINATION_SWEEP/order=0, with no BP. Returns owned correction(n) and original-H validity. |

The production hybrid uses the same C++ sessions directly; it never transfers edge
arrays through Python between cycles. `Graph` constructs canonical row-major edge
IDs through ldpc's sparse graph infrastructure and stores flat CSR/CSC arrays.
Variable reductions follow increasing check order. Two minima handle repeated
minimum magnitudes and zeros; zero signs are positive, degree-one check messages
are signed clip limits, and degree-zero contradictions are checked explicitly.
Hard decision is L<=0. Clipping normalizes signed zero. Extrinsic messages subtract
from unclipped S, never clipped L. Arithmetic uses binary64, no fast-math and no
FP contraction. A valid BP result may disagree with any finite hint.

OSD owns its graph and probability buffers before constructing the upstream object
that references them. Destruction order is safe. Setup performs upstream reusable
preparation outside shot timing; each decode includes copies, signed-LLR sort,
fast_solve elimination and full-H validation. No combination candidates or hidden
BP object exist in the bridge. Empty dimensions are handled algebraically, and
rank-deficient/inconsistent syndromes return explicit invalid results after parity
validation. Equal-LLR ordering retains upstream qsort semantics; compiler/libc and
native binary identities are recorded, with no cross-platform tie guarantee.

## Search and orchestration

`native/hybrid_model.hpp` owns immutable graph/prior/observable mappings and each
detector's (physical weight,column) order. `hybrid_search.hpp` owns a contiguous
node arena with parent IDs and zero-assignment deltas, packed residual words,
byte-addressable working assignments, cached canonical keys and exact rank fields.
Expansion and unused-guidance heaps are independent. Consuming a hint does not
remove its expansion node, and expanding a node does not remove its hint. Used
hints are removed once; residuals alone are never used to merge nodes.

The first active residual row supplies free U. Child k selects its kth column and
forbids earlier free columns, leaving later ones free. The first generated goal
returns immediately, including a depth-D goal; it has no minimum-cost certificate.
Generated locally consistent nonterminal nonroot nodes are eligible hints even at
D. The root counts as one generated node, except the zero-syndrome shortcut which
returns before root creation. `search_depth_limited` counts every constructed
nonterminal depth-D node, including a D=0 root and locally rejected depth-D children;
`search_rejected_local` is a separate, potentially overlapping count.

The production heuristic computes all active-column degrees once per node and
uses reusable reduction buffers. The reference path recomputes each candidate's
active degree directly and selects queue minima by linear scans. Both sum g over
sorted selected indices and h through the same zero-padded balanced binary tree.
There are no epsilon comparisons. This implementation does not cache heuristic
leaves across different nodes, so no incremental affected-detector closure or
speculative early scan termination is needed. Those optional optimizations remain
deferred. Cached keys/residual vectors still allocate per node; no allocation-free
or logical-performance advantage is claimed.

`hybrid.hpp` runs search first, one best unused hint per attempt, warm or cold
min-sum blocks, then direct OSD on the latest stored L or clipped physical weights.
Global depth/node and per-cycle work budgets persist across slices. A node cap is
checked before another child construction; it triggers immediate fallback without
heap truncation. Prefix CPU limits are checked before expansions, children, hint
transitions and full iterations. CPU checks precede the child-cap check when both
would fire. Prefix limits do not cap atomic-operation overruns or OSD/full service.
Allocation overflow/failure is explicit; the configured node cap bounds arena size
but does not guarantee that the machine can allocate that amount of memory.

The native test-only `reference=True` constructor and `hybrid_score` entry point
permit differential/exhaustive checks; they are not alternate YAML profiles.
All kernel phases, pattern selection, diagnostic counters and orchestration loops
are C++17. No search or BP production loops are implemented in Python.

## Telemetry supplied for Stage 4

`hybrid_telemetry.hpp` defines enumerated terminal stages/reasons, fallback reasons,
LLR sources and phases. `Result.summary` is compact and owned. It contains the
HSBP-EXP counters, cap flags, last-hint assignment counts, final hint disagreements,
OSD reach/call/order/source, phase sums and prefix aggregates/residuals. Enum names
are converted to strings in the native binding. No JSON is formatted in hot loops.

Native CPU uses CLOCK_PROCESS_CPUTIME_ID; wall uses CLOCK_MONOTONIC. Both yield
signed-int64 nanosecond durations. One record describes each actual phase call;
there is no per-node/per-edge clock instrumentation. A zero-budget search call is
an actual call when a frontier exists; a missing frontier produces no search event.
Failed phase calls retain measured durations and an exception result. Completed
iteration counters count only fully completed iterations, including those before
an exception. Prefix overlaps search/transition/iteration phases; never add both.
`prefix_other` is prefix minus these constituent durations, without clamping.

One round record is exported per started cycle with before/after pool sizes,
configured and actual work, selected hint statistics and a canonical digest.
The digest is lowercase 16-digit FNV-1a64 over sorted pairs encoded as little-endian
uint32 column plus uint8 bit. It is diagnostic only; exact keys determine identity
and ties. Round `residual_before` is the previous BP decision's residual just before
hint replacement, or the immutable physical-channel hard decision on the first
attempt. `residual_after` follows the attempt. No hidden initial BP is performed.
Unselected hints and absent BP residuals are null. Cycles complete only after
nonterminal, non-hard-cap work; the final ordinary fallback cycle can count complete.

The adapter returns lightweight summaries inside service time. `export_telemetry`
converts/copies phase and cycle buffers outside that service, before the next shot.
A valid event is the terminal candidate, whose prediction is already in DecodeResult;
The worker attaches it and evaluates logical labels outside timing. Search events
without a returned correction have null candidate validity. No native event has
truth-dependent labels. Stage 4 storage implements service_other, clock metadata,
Arrow types/foreign keys, event truth labels and atomic v2 manifests/tables.

## Source restoration, builds and evidence

The existing `screened-decimation-bp` fork branch and upstream remote are preserved.
All upstream kernel files remain byte-identical; opt-in additions are recoverable
from `external_lib/patches/ldpc.patch`, including ignored bindings.cpp and type stubs.
`ldpc.hybrid_bp.source_files.SOURCE_FILES` is the exact fork source/build inventory,
covering the new graph/session/bridge, binding/shim/stub, build script and transitive
pinned headers. The manifest audit and run archive include every listed file.
`native_sources.HYBRID_PROJECT_FILES` covers every project hybrid header, binding,
CMake and inventory script. CMake embeds both aggregate hashes, watches incremental
build inputs, and uses absolute paths so automatic reconfiguration works from the
build directory. Runtime checks reject stale, missing or modified sources/binaries.

Activate search_decimation before running:

```bash
(cd external_lib/ldpc && python setup_hybrid.py build_ext --inplace)
python python_scripts/audit_dependencies.py
python -m pip install --no-build-isolation --no-deps -e .
scripts/build_dependencies.sh --check
python -m pytest -q
python tests/check_hybrid_restoration.py
```

The restoration command creates a temporary pristine worktree, applies the tracked
patch, compiles a new binding without old binaries, validates the aggregate digest,
runs min-sum/OSD checks and removes the worktree. It uses the existing environment;
it is not a claimed fresh conda or full-dependency build. Build reference_bp with
setup_reference.py separately if its four hashed files change. Preserve pybind11
2.11.1 and sequential Stim builds.

For native tests, configure Release/Debug with `-DQEC_BUILD_TESTS=ON`, the active
Python executable and pybind11_DIR; add `-DQEC_SANITIZE=ON` for the sanitizer build.
Build `test_reference_bp test_search test_hybrid_bp test_hybrid`, then run ctest with
`--output-on-failure`. Sanitizer runs use ASAN_OPTIONS=detect_leaks=1 and
UBSAN_OPTIONS=halt_on_error=1. Exact paths, results and deviations are in STATUS.md
and docs/test_results/hybrid_stage_*.log.

Engineering timing on one fixed 80-check/180-mechanism fixture, 100 resets/searches,
constructed 22,800 nodes in both paths: reference 87,122 us, optimized 38,931 us.
This development measurement has uncontrolled host load, excludes OSD and does not
measure logical failure or establish a speedup on physical benchmark problems.
`tests/native/benchmark_hybrid_search.cpp` preserves the seed/fixture and work.

Stages 4–5 now supply saved experiment tables, timing accounting and paired
hypothesis analysis/notebook. Stage 6 restoration/build and end-to-end acceptance
are documented in hybrid_acceptance.md. No production physical-rate sweep or scientific advantage is claimed.

## Equation-to-API map

The immutable graph stores physical weights `w_i = log1p(-p_i) - log(p_i)`.
`SearchSession` uses `r = s XOR H 1_F1`, `g = sum(i in F1) w_i`, and
`h = sum(a with r_a=1) min(i free adjacent to a) w_i/k_i`, where `k_i` counts
active residual neighbors. Its exact queue key is `(g+h, residual_weight, canonical
pattern)`. The reference and optimized paths use the same fixed binary reduction
for h, branch order and goal-on-generation behavior; this is a bounded first-valid
search, not an optimum certificate.

`StatefulMinSumSession.replace_hint` replaces physical fields with
`c_i=(1-2*b_i)*(w_i+margin)` on selected finite-hint bits; these finite channel fields remain unclipped,
and other fields return to physical weights. The variable pass computes
`S_i=c_i+sum_a z_ai`, `L_i=clip(S_i)`, `q_ia=clip(S_i-z_ai)` in canonical edge order.
The check pass consumes previous q, multiplies signs with `(-1)^s_a`, and uses the
scaled minimum magnitude excluding i. Degree-one output is the signed clip limit;
sign(0) is positive and the hard decision is `L_i <= 0`. Hint replacement retains
check messages within a warm shot; reset invalidates them for the next shot.
See the normative specification for full boundary/overflow equations and the
independent tests/min_sum_oracle.py for edge-exclusion arithmetic checks.

`Osd0Bridge.decode(s,L)` receives the final clipped L or clipped channel weights,
sorts through the pinned signed-LLR kernel and runs order-zero fast_solve. Original
H validates the correction; A predicts all observables. No truth enters these APIs.
