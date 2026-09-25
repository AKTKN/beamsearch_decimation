# AF-BP Stage 7 final validation (2026-09-25)

The active package remains `af_bp`, `relay_bp`, `beam8`, and ordinary `bposd`.
Stage 7 changed validation tests, the clean bootstrap and documentation, with
no scientific kernel or simulator physics/sampling/truth/worker/timer edits.
The final implementation report is `docs/af_bp_final_report.md`.

Final evidence in `search_decimation`: **103/103** active Python tests,
**53/53** focused baseline/Relay/config/storage tests, native Debug, ASan and
UBSan each **7 graph + 6 decoder groups**, 12 selected upstream ldpc tests,
7 selected Relay upstream tests, and 112 exact pristine-versus-patched Beam
decisions. The isolated pinned-source build in
`assets/acceptance/20260925T131529.418408Z_27f6592bd8` completed and
audited source/patch/import/native identities with no copied binaries or
circuit cache. Its first full suite found a missing pristine BP-OSD test
wheel; an independent no-binary clone of the exact ldpc pin was built and
installed into that clean workspace, then the full suite passed **103/103**,
including all 288 pristine BP-OSD comparisons. The reusable clean builder now
includes this test-wheel step. The same clean prefix passed 19 selected ldpc
and Relay upstream tests and `pip check`.

The bounded two-shot four-decoder serial/two-worker surface runs each wrote
eight exact-schema rows with all non-latency values equal. A one-shot BB144
d12/R1 run wrote four exact-schema rows. Live BB144 AF-BP graph work used
H `(144,864)` with 2,952 edges and applied four factorizations; the
whole-process high-water RSS was 273,416 KiB. Production candidate scoring
uses no candidate-times-E/N storage. The requested negative net-cycle-gain
fixture is impossible for valid bicliques and the specified nonnegative
weights; the report gives a proof. No production sweep or performance claim.

---

# AF-BP Stage 6 active benchmark integration (2026-09-25)

`af_bp`, `relay_bp`, `beam8`, and ordinary `bposd` are active comparison
profiles on identical physical shots. Strict AF-BP config maps every Stage-4
scientific setting, including graph/failure/U selection, factorization,
parallel/serial/qDither, budgets, Min-Sum scaling, and seeds. New saved rows
use the exact five-field `benchmark_results/2` schema. Active figures now
include mean total BP iterations; historical multi-schema plotting remains
under `analysis/legacy/`. Sampling, truth, seed derivation, worker scheduling,
BB144 circuits, timing boundaries, and native scientific kernels were not
changed.

Final `search_decimation` evidence: 102/102 full Python tests passed, including
paired four-decoder syndrome equality, serial/two-worker non-latency row
equality with Relay stochastic legs disabled, all four BB144 adapters, exact
failure accounting, active/legacy schema routing, and synthetic/smoke plots.
All six bounded config examples validated. The two-shot AF-BP surface d3
smoke, two-shot AF-BP parallel/serial/qDither example, and one-shot BB144
d12/R1 all-decoder smoke completed; the BB144 run
retained AF-BP and Relay failure iterations under intentionally tiny budgets.
The dependency build check passed. No production sweep was run. See
`docs/af_bp_stage6.md` for exact paths, limits, and the active surface.

---

# AF-BP Stage 5 comparison decoders (2026-09-25)

The active truth-free comparison surface is now `beam8`, `bposd`, and
`relay_bp`. Relay uses unmodified upstream Apache-2.0 Rust/Python source at
verified commit `d185194ba0cb4101ced4340d82b2ee6d42f225f0`, locked
maturin, F64 single-shot `decode_detailed`, and its exact total
`DecodeResult.iterations`. It exposes the requested algorithm settings;
`explicit_gammas` is rejected until a reproducible array-source contract
exists. Existing Beam8 instrumentation and BP-OSD actual iteration counts
remain in place. AF-BP and qDither are not registered in the simulator.

Final verification in `search_decimation`: 92/92 Python tests passed;
the focused Relay/config/Beam8/BP-OSD suite passed 51/51, including strict
config discovery.
The pinned build/import/source audit and `pip check` passed. A pristine Beam
build supplied 16 reference decisions and convergence results, all matched
by the instrumented build. Relay's impossible-syndrome case counted 14
iterations across initial and three relay legs; BB144 one-round construction
and decode smoke passed. Two-shot Relay and paired Beam8/BP-OSD surface d3
smokes completed with the existing five-field output. Circuit sampling,
worker scheduling, timing and storage code were unchanged. No production
sweep ran. See `docs/af_bp_stage5.md` for paths and limits.

---

# AF-BP Stage 4 native service (2026-09-25)

The AF-BP-1.0 native service now composes the Stage-2 fork BP engines with the
Stage-3 standalone graph core. It supports initial_parallel, independent hard
initial/transformed iteration budgets, parallel/serial/qDither, deterministic
seed policy, graph-warm marginal relay, sequential n_fact transforms, original-H
validation, A prediction and exact total BP iterations. There is no OSD or
truth input. `qec_bp_benchmark.af_bp_service` marshals one native call per shot.
The service is built as a separate CMake target but is not registered in the
simulator; config/storage/plots remain baseline-only.

In `search_decimation`, the editable CMake build and source-hash audit passed;
the full Python suite passed 84/84, including six native service integration
groups and the existing graph/fork and baseline regressions. The six service
groups also passed with ASan/UBSan, warnings as errors and no fast-math.
`validate_config.py config/baselines.yaml.example` passed and `af_bp_v1`
remained rejected by the active config registry. No production sweep ran.

---

# AF-BP Stage 3 graph core (2026-09-25)

The standalone C++17 `src/af_bp_core/graph.hpp` now provides sparse mutable
physical/auxiliary graph state, immutable physical H0/s0, sparse XOR support,
physical residual/history weights, pair-seeded closed bicliques, exact
factorization, and local weighted net-cycle scoring. Candidate A/B selection
is sequential with rediscovery. No complete AF-BP decoder or simulator
registration exists. See `src/af_bp_core/README.md` for ownership and bounds.
The native oracle includes exhaustive physical lifts, randomized small graph
delta comparisons, nested support, 20,000-variable sparse support, and policy
cases. In `search_decimation`, the final full Python suite passed 81/81,
including native C++ compilation/execution. The same six native groups passed
with `-fsanitize=address,undefined`, `-fno-fast-math`, and warnings as errors.
No production simulation was run.

---

# AF-BP Stage 1 active reset (2026-09-25)

The active `af-bp-v1` branch now registers only `beam8` and configurable-order
`bposd`. AF-BP, Relay-BP and qDither are not implemented. Decimation families
are archived under named legacy paths and excluded from active config and CMake.
The physical simulator, BB144, pairing and decoder-service timing boundary are
preserved. New baseline rows use `baseline_results/1` with exact total BP
iterations. Historical scientific results and the previous source reports below
remain unchanged. See `docs/legacy/decimation/README.md`.

Stage-1 verification in `search_decimation`: 72/72 active Python tests passed;
48/48 focused baseline/config/import/regression tests passed; editable project
build and `scripts/build_dependencies.sh --check` passed. Both the paired Beam8
and BP-OSD order-10 smoke (two shots) and BP-OSD order-0 smoke (two shots)
completed. A paired two-worker smoke had exact non-latency row equality with
the serial run (four rows). Active summary and three plotting functions read
the saved five-field output. A historical SEARCH-BP/LPM-DP reader returned 15
summaries from an existing old run. Beam instrumentation patch restoration and
rebuild passed in a clean temporary clone; patched and pristine Beam decisions
and convergence agreed on all 16 four-bit syndromes in the focused comparison.
No production sweep was run. These smoke counts make no performance claim.
Prior evidence below belongs to the pre-migration implementations.

---

# LPM-DP-BP-1.0 final validation (2026-09-23)

Final validation preserves the Stage-4 `LPM-DP-BP-1.0` scientific and simulator
paths. The final call graph contains only initial BP, per-parent polynomial LPM-DP
candidate generation, structural fixation, warm child BP, bounded post-BP
retention and optional one-time OSD-0. It contains no SEARCH-BP solve/guide,
admission, Tesseract/A*, frontier search or exponential fixation enumeration.
Python still performs one truth-free native call per shot, and saved results remain
the exact five-field `lpm_dp_results/1` contract.

The final clean-build audit found and corrected two bootstrap-only omissions:
the pristine restoration inventory did not copy the required untracked
`src_cpp/decimated_bp.hpp`, and pandas was declared in `pyproject.toml` but absent
from `requirements.lock.txt`. The restoration list and dependency lock now cover
both, with a derived provenance regression for every untracked hybrid input.
Neither correction changes decoder numerics or simulator physics.
The recursive config test also correctly treats preserved SEARCH-BP-v2 templates
as legacy expected-invalid inputs, eliminating the previously documented
test-discovery-only failure without changing parser behavior.

Executed in `search_decimation` without a production sweep:

- isolated build `assets/acceptance/20260923T062443.251415Z_77b03b3e46`
  completed from new pinned checkouts and a new conda prefix, without copied
  native binaries, wheels, build directories or circuit cache;
- dependency, fork and native source identity checks plus `pip check`: passed;
- complete project pytest: **337 passed, 1 skipped** in both the working and
  isolated clean environments; the skip is an unavailable historical artifact;
- focused LPM-DP, exact-BP, Beam Search, BP-OSD and SEARCH-BP regressions:
  **128 passed**, including all 288 pristine/fork BP-OSD comparisons;
- selected upstream ldpc BP tests: **12 passed**, with six existing warnings;
- fresh native Debug CTest: **9/9 passed**;
- ASan/UBSan CTest with leak detection and halt-on-error: **9/9 passed**;
- pristine-fork restoration, both bindings, identities and native CTest:
  **9/9 passed**;
- one-worker serial versus two-worker spawn Surface-d3 smoke: every non-latency
  saved value, including `osd_called`, matched for LPM-DP, Beam and BP-OSD;
- representative bounded native workload: exact vector payload **1,896 bytes**,
  measured process peak RSS **4,436 KiB**.

The active minimal runner deliberately has no retained-sample replay, so no replay
claim is made. The final ownership audit proves at most B old snapshots, B online
retained child snapshots and one reusable full session, bounded candidate/DP
scratch and exact `NW` history; it has no raw-candidate-times-N/E term. The exact
formula, BB72 bound, file inventory, limitations and separate appendix assessment
of deletion-biased retention are in
[docs/lpm_dp_final_report.md](docs/lpm_dp_final_report.md). The proposed debiased
score is not part of the reference decoder and is reserved for a named future
ablation.

---

# LPM-DP-BP-1.0 Stage 4 simulator integration (2026-09-23)

Integrated the existing native Stage-3 decoder with the simulator under the
distinct kind/profile `lpm_dp_bp` / `lpm_dp_bp_v1` and fixed algorithm version
`LPM-DP-BP-1.0`. The strict `lpm_dp_config/1` model contains only the 14 settings
from the note, with reference defaults and native-compatible bounds. The Python
adapter constructs one native decoder per worker and makes exactly one
truth-free native `decode(syndrome)` call per shot; all candidate generation,
fixation, BP, retention and optional OSD control remain native.

LPM-DP writes `lpm_dp_results/1`, an exact five-column schema containing
`shot_id`, `decoder_name`, `logical_error`, `latency_ns` and the native
`osd_called` flag. Native declared failures carry no synthesized correction and
are counted as logical errors. The existing complete-service timer is unchanged.
Circuit/DEM construction, noise, sampling, syndrome and truth generation, seed
derivation, scheduling, and truth comparison were not edited. The only runner
and storage changes route the selected minimal result schema. No production
sweep was run; the bounded Surface-d3 integration check used two shots.

Executed in `search_decimation`:

- Stage-4 focused configuration, binding, adapter, result-contract and paired
  simulator tests: **4 passed**;
- deterministic Beam Search, BP-OSD and SEARCH-BP regression selection:
  **76 passed**, unchanged from Stages 2 and 3;
- exact-message decimated-BP plus selected upstream ldpc BP tests:
  **24 passed** with six existing warnings;
- native Debug CTest: **9/9 passed**;
- ASan/UBSan CTest with leak detection and halt-on-error: **9/9 passed**;
- dependency/source audit, editable source-hashed extension rebuild and strict
  example validation: passed;
- isolated pristine-fork restoration, both opt-in binding builds, source
  identities and native CTest: **9/9 passed**;
- full project pytest: **335 passed, 1 skipped, 1 failed**. The only failure is
  the same pre-existing legacy SEARCH-BP-v2 config-discovery mismatch recorded in
  Stages 1-3; no LPM-DP or old-decoder regression failed.

Full contracts and the simulator-core diff audit are in
[docs/lpm_dp_stage4.md](docs/lpm_dp_stage4.md). There are no LPM-DP numerical
changes from Stage 3 and no changes to existing decoder behavior. Stage 5 has not
started.

---

# LPM-DP-BP-1.0 Stage 3 native decoder (2026-09-23)

Implemented the distinct native-only `lpm_dp_bp` / `lpm_dp_bp_v1` decoder state
machine. It uses the Stage-1 per-parent local-parity generator, Stage-2 exact
check-message snapshots, structural hard fixation, warm-started parallel min-sum,
the main-note post-BP retention order and an optional one-time OSD-0 fallback.
SEARCH-BP search, solve/guide scoring, global admission and search corrections are
not used. No Python binding, configuration, adapter, worker or simulator route was
added; Stage 4 has not started.

Execution is bounded to eight old parents, eight online-retained full child
snapshots and one reusable session at reference settings. Noncompetitive children
are never snapshotted, and the worst retained child is destroyed before a
competitive replacement is captured. The parent mean is derived after snapshot
restore rather than stored redundantly. For BB72 d6/r6 at the reference defaults,
the final-cycle vector-payload bound is 5,218,344 bytes and 5,223,048 bytes with
the validation ABI's inline state/session/temporary objects. There is no
`raw_candidate_count*E` or `raw_candidate_count*N` term. The focused fixture's
bound is 1,896 bytes and its measured process peak RSS is 4,308 KiB. Full formulas
and exclusions are in [docs/lpm_dp_stage3.md](docs/lpm_dp_stage3.md).

Executed in `search_decimation`:

- native Debug CTest: **9/9 passed**;
- ASan/UBSan CTest with leak detection and halt-on-error: **9/9 passed**;
- exact-message decimated-BP Python tests: **12 passed**;
- selected upstream ldpc BP tests: **12 passed** with six existing warnings;
- deterministic Beam Search, BP-OSD and SEARCH-BP regression selection:
  **76 passed**, matching the Stage-2 baseline;
- dependency/source audit and editable source-hashed extension rebuild: passed;
- isolated pristine-fork restoration, both opt-in binding builds, source identity
  checks and native CTest: **9/9 passed**;
- full project pytest: **331 passed, 1 skipped, 1 failed**. The only failure is the
  same pre-existing legacy SEARCH-BP-v2 config-discovery mismatch recorded in
  Stages 1 and 2; no LPM-DP or old-decoder regression failed.

There are no deviations from the main-body retention rule. The implementation
uses the decimation session's documented running-sum addition order for the clipped
history mean, a convention explicitly permitted by the note; the appendix's
debiased retention is absent. No existing decoder numerical behavior changed.

---

# LPM-DP 1.0 Stage 2 exact final check messages (2026-09-23)

The Stage-0 audit conclusion was confirmed: the fork computed the exact final
check-to-variable array used by each completed parallel BP round, but kept it in
a session-only workspace and zeroed it on snapshot restore. LPM-DP therefore
could not receive the required `mu_(a->j)^(T)` for an arbitrary retained parent.

The minimal fork change moves that existing `E`-double buffer into the owned
decimated-BP snapshot and adds native/Python read-only `check_to_variable`
accessors. There is no duplicate session buffer and no recomputation. Snapshot
restore now preserves the exact array; descendant reconstruction zeros both
message directions on fixed columns. Default snapshot copy/move semantics own or
transfer all arrays. BP update equations, stopping, decisions and all decoder
controllers are unchanged. The exact ownership and memory audit is in
[docs/lpm_dp_stage2.md](docs/lpm_dp_stage2.md).

For the largest checked-in model (BB72 d6/r6, `M=252`, `N=2232`, `E=7776`) at
`W=8`, snapshot vector payload rises from 243,252 to 305,460 bytes; eight parents
use 2,443,680 bytes; the reusable session remains 307,944 bytes; and one
materialized child uses 305,460 bytes. Including validation-ABI inline objects
but excluding allocator bookkeeping, the corresponding requested live figures
are 305,692, 2,445,536, 308,248 and 305,692 bytes. The conservative simultaneous
total is 3,059,476 bytes. No allocation is proportional to raw candidate count
times `E` or `N`.

Fork source changes are exactly `src_cpp/decimated_bp.hpp`,
`src_python/ldpc/hybrid_bp/bindings.cpp` and
`src_python/ldpc/hybrid_bp/__init__.pyi`; the tracked patch, manifest and build
identity were regenerated. Executed in `search_decimation`:

- exact-message/restore/fixation Python fork tests: **12 passed**;
- selected upstream ldpc BP tests: **12 passed** with six existing warnings;
- deterministic Beam Search, BP-OSD and SEARCH-BP regression selection:
  **76 passed**, matching the pre-change baseline;
- native Debug CTest: **8/8 passed**; ASan/UBSan CTest with leak detection:
  **8/8 passed**;
- dependency check, fork/source audit, hybrid binding rebuild and editable project
  rebuild: passed;
- isolated clean fork restoration, both binding builds, identity checks and native
  CTest: **8/8 passed**;
- full project pytest: **331 passed, 1 skipped, 1 failed**. The only failure is the
  same pre-existing legacy-config discovery mismatch recorded by Stage 1; no
  LPM-DP, BP, Beam, BP-OSD or SEARCH-BP regression failed.

No numerical behavior changed. Stage 3 was not started.

---

# LPM-DP 1.0 Stage 1 standalone candidate generator (2026-09-23)

Implemented the standalone C++ candidate generator from
`local_parity_decimation_note.tex`: exact eight-parameter validation, immutable
parent summary, sparse shared-check selection, nested fixation locations,
edge-aligned cavity fields, joint one/two-check sum-product and top-K DP, complete
local normalizer/retained mass, and largest-q selection through q=64. The generator
returns canonical patterns and normalized local log probabilities. It contains no
old solve/guide scoring, assignment enumeration, recursive BP, beam retention,
OSD, bindings or simulator integration. The BP fork and scientific artifacts are
unchanged.

New native headers are source-identity inputs. CMake adds `test_lpm_dp`; its
independent exhaustive oracle checked 600 deterministic random models (576
feasible, 24 infeasible) and 1,646 fixation marginals, plus explicit history,
region, cavity, worked-example, empty-boundary, ordering, q=64, mass, fallback,
infeasibility, validation and end-to-end cases.

Executed in `search_decimation`:

- focused Debug test: passed;
- focused ASan/UBSan test with leak detection: passed;
- complete Debug native CTest: **8/8 passed**;
- `scripts/build_dependencies.sh --check`: passed; the editable source-hashed
  project extension rebuilt successfully;
- `python tests/check_hybrid_restoration.py`: restored both fork bindings, rebuilt
  a fresh project extension, verified source identities and passed native CTest
  **8/8** after adding the new target to its explicit build list;
- full `python -m pytest -q`: **331 passed, 1 skipped, 1 failed**. The sole failure
  is pre-existing branch inconsistency in
  `test_cs0_identity_and_legacy_parameters`: its recursive template scan treats
  tracked `config/legacy/search_bp_v2/search_bp.yaml.example` as current even
  though that preserved file declares schema `/3`, SEARCH-BP-2.0 and results-v1
  while current validation requires `/4`, SEARCH-BP-2.1 and results-v2. Neither
  file is changed in this stage; all LPM-DP and other collected tests passed.

The derived live-memory bound is
`O(n+m+M d_v^2+|V_A|+S K q0)` once per parent and `O(q0)` per returned candidate;
there is no unbounded frontier or `2^q`/`2^|B|` storage. At default `S=4,q0=4,K=2`,
the DP allocation payload subtotal described in `docs/lpm_dp_stage1.md` is 1,968
bytes on the validation ABI, excluding sparse-map allocator overhead, parent-wide
summary arrays, outer objects and owned results.

---

# SEARCH-BP-2.0 final validation and conservative optimization (2026-09-22)

Completed the seven-step TeX-to-function audit in
[the active implementation document](docs/search_bp_implementation.md), including
exact defaults/schema, numerical conventions, ownership and memory bounds.
Root refined.tex, fork BP/OSD, physics/sampling and all baseline kernels are unchanged.
SEARCH-BP-1.0 remains legacy-only. The active fork supplies BP; project C++ owns
all search, global dual-score admission, R retention and highest-R OSD-0 control.

Production edits are limited to two headers: `search_bp_search.hpp` reserves branch
prefixes before copying and sizes reusable descendant scratch by visited check
rather than N; `search_bp_decoder.hpp` reserves the first generated candidate batch,
keeps vector geometric growth across subsequent parents and checks size overflow.
No scores, order, budget, pruning, recursion or fallback convention changed.

Added randomized scalar checks across 32 synthetic graphs and 512 candidate
patterns, explicit tight floating-point tolerances/exact GF(2), and Surface d3 /
BB72 d6 correction-level fresh/reused/reset tests (all 12 BB observables). Existing
independent ring/BP, tree, admission, R/retention/fallback tests remain active.

Executed in search_decimation, with final-source logs under
`docs/test_results/search_bp_final_*`:

- `scripts/build_dependencies.sh --check`: passed; no fork patch/manifest
  regeneration required because external source/build bytes are unchanged.
- `python -m pip install --no-build-isolation --no-deps -e .`: rebuilt successfully;
  final runtime/source identities verified.
- Focused BP/Stages 3-5 pytest: 115 passed; final full `python -m pytest -q`:
  **330 passed, 1 skipped in 27.76 s**. Skip is the unavailable historical local
  acceptance artifact. Full suite includes all focused tests after the final edits.
- Selected upstream ldpc BP tests: **12 passed**, six existing legacy/OpenMP warnings.
- All seven standalone native targets: **Debug CTest 7/7**, **ASan/UBSan CTest 7/7**
  (leak detection, halt-on-error). Exact directories/options in active document.
- `python tests/check_hybrid_restoration.py`: restored pinned fork plus patch,
  rebuilt both opt-in bindings and fresh project extension, checked hashes;
  **7/7 native tests passed**. This reuses installed conda dependencies, not a
  fresh-environment rebuild.
- Config validation passed. Explicit serial and two-worker CLI smoke runs on
  Surface d3 / BB72 d6 at validation p=.003, four shots per condition, SEARCH-BP /
  beam8 / CS0: **24 rows per run**, exact scientific equality excluding latency,
  exact five-column schema and only `data/` plus resolved config. Paths/evidence
  are in `search_bp_final_smoke_validation.json`; no production sweep.

Decoder-only synthetic benchmark: 64 checks, 128 variables, degree eight,
contradictory duplicate checks to exercise two cycles/fallback, seven alternating
before/after process pairs, 1,600 timed decodes per policy per process. Median of
process means (microseconds/decode): **fixed_root 951.228 -> 949.949**;
**refresh_descendant 950.167 -> 963.153**. Observed ranges overlap. This does not
show a latency improvement; the changes reduce avoidable allocation/storage only.
All stress cases fail by construction; successful-path equivalence is covered by
independent behavioral tests, not the benchmark checksum. Baseline gprof sampled
about 52.9% in BP iterations and 31.0% in existing OSD sorting/row addition.
Python adapter-only profiling identified binary validation and H/A multiplication;
independent validation was preserved. Quantum simulation was not profiled.

One `/usr/bin/time -v` process each reported **4532 KiB before / 4136 KiB after**
peak RSS, including runtime/allocator/OSD. These are coarse observations, not a
measured per-state footprint or a general memory improvement. Live-state bounds
are documented analytically; no large physical-model peak was measured. No
accuracy, throughput, tail or advantage claim follows from this bounded evidence.
Earlier final-pass iterations are preserved with `_initial` filenames.

Updated AGENTS, README, STATUS, active implementation/integration/build/traceability
and minimal-output docs, native/tests READMEs and smoke-config comments. Historical
stage evidence and legacy scientific documents are preserved.

# SEARCH-BP-2.0 Stage 5: simulator integration (2026-09-22)

Integrated `SearchBP` with the existing truth-free DecoderAdapter and complete
native `SearchBP2Decoder`. Every validated mathematical setting maps directly to
native Settings, including newly exposed min-sum scaling. Python does not score,
search, select candidates or construct SEARCH-BP event dictionaries. The adapter
independently validates original H/s and predicts all A observables inside the
existing complete-service timer. Native OSD usage is preserved exactly.

The strict nested SEARCH-BP-2.0 config now enforces positive int32 counts,
k_keep <= k_run, **q <= m for both local policies**, full history-window budgets,
finite bounded clip, finite scoring/scaling coefficients and native_threads=1.
OSD-0/binary64/no-fast-math are fixed; fallback/numerics sections and old SEARCH-BP
controls are rejected. refresh_descendant remains the default. The native test
API's broader q capability is unchanged; simulator configuration follows the
Stage-5 constraint.

Workers normalize directly to five scalar fields and no longer build/transport
raw-sample rows, wide decoder records or event dictionaries. The simplified
ResultStore owns the single five-field schema and writes one
`data/<condition>_results.parquet` per condition. Grouped shot flushing and bounded
batch backpressure remain. New runs contain exactly config_resolved.json and data/.
The reader directly summarizes rate/Wilson bounds, mean/median/p95/p99 wall latency
including failures, and OSD fraction with known/unknown denominators. Earlier
minimal `_logicalerror.parquet` files remain readable, without rewriting artifacts.

Exact schema: shot_id:string nonnull; decoder_name:string nonnull;
logical_error:bool nonnull; latency_ns:int64 nonnull/nonnegative;
osd_called:bool nullable only for an opaque baseline. SEARCH-BP requires an exact
boolean. No corrections, predictions, costs, statuses, telemetry, phase clocks,
samples, identities/hashes or counters are persisted as result fields.

No circuit/noise/schedule/provenance/DEM/physical-sampling/truth-generation/seed/
pairing/logical-error convention changed. The source audit verifies unchanged
physics and baseline config ASTs, physical-source bytes, sampler/scheduling ASTs,
shot-ID expression, failure-label function and all native/fork inputs. No native
rebuild or patch regeneration was needed. No production sweep was run.

Actual commands in search_decimation (docs/test_results/search_bp_stage5_*):

| Command / evidence | Result |
|---|---|
| `python -m pytest -q` | **327 passed, 1 skipped**, 30.60 s |
| New integration tests | **28 Stage-5 cases passed** within the full suite |
| Paired smoke integration | Surface d3 + BB72 d6, four shots each, SEARCH-BP/beam8/CS0, one and two workers; identical scientific rows, exact pairing, 24 rows per run, only five fields and two-entry directory layout |
| Controlled worker service | Same syndrome object delivered to both decoders; exact failure/mismatch semantics; 18 ns simulated complete-service latency including failure handling, excluding simulated sampling/truth-comparison time; exact/null OSD preservation |
| `scripts/build_dependencies.sh --check` | passed; existing native hashes current |
| `python python_scripts/validate_config.py config/search_bp.yaml.example` | passed |
| Source audit | search_bp_stage5_source_audit.json; physics/sampling/seed/label/native inputs verified unchanged |
| `git diff --check` | passed |

The first config-boundary tests exposed a collision with the existing hybrid's
zero-allowing NativeCount alias. SEARCH-BP now uses a separate PositiveNativeCount;
zero counts reject cleanly before the history overflow guard. Initial failing logs
are preserved; the final full suite passes. Native Debug/sanitizer/restoration
sources and binaries are unchanged from Stage 4's passing seven-target checks.

Changed implementation: config.py, decoders/__init__.py, runner/worker.py and
pipeline.py, storage/results.py, analysis/simple_search_bp.py, smoke template,
focused integration/contract/storage tests and affected docs. See
[docs/search_bp_stage5.md](docs/search_bp_stage5.md) for the complete native mapping,
saved schema, example directory tree and source/test traceability.

---

# SEARCH-BP-2.0 Stage 4: recursive native decoder (2026-09-22)

Completed Steps 5–7 as `_native.SearchBP2Decoder`: one global cycle pool,
dual-score quotas, exact full-pattern deduplication and guide-first refill;
strict descendant BP inheritance; post-BP R ranking and top-K_keep retention;
fresh search each recursive cycle; direct OSD-0 fallback exactly once on exhaustion.
K_run bounds the whole cycle, not each parent. The native result exposes only
valid, correction, prediction, physical_cost and osd_called. The simulator adapter
remains guarded, as requested. No simulator integration or production simulation.

The user explicitly approved final signed posterior LLRs for OSD with fixed
infinities replaced by signed DBL_MAX. Free LLRs are unchanged. Highest-R retained
state supplies the vector, or physical channel priors if the final beam is empty.
Every successful result is independently validated against original H/s and A.
Locally contradictory instances cannot produce feasible descendants and have no
full history; they are discarded before retention. Old parents are not preserved
when a cycle produces no viable children.

Admission ties: relevant score, canonical full pattern, parent ID, delta, then
occurrence index. Quotas precede deduplication; the first selected occurrence is
the donor. Retention ties: descending R, full pattern, state ID. No diversity rule
beyond exact duplicate patterns. Snapshots move through partial selection; discarded
states are destroyed immediately. Search pools/heaps never survive a cycle.
One decoder object rejects overlapping/reentrant calls before mutating state.

Source changes: new `native/search_bp_admission.hpp` and `search_bp_decoder.hpp`,
small binding additions, source inventory/CMake, the seventh restoration/native
test target, `tests/test_search_bp_stage4.py`, and affected documentation. No fork,
patch, normative TeX or Stage-3 numerical/search implementation changed. The full
stage contract, traceability and bounds are in [docs/search_bp_stage4.md](docs/search_bp_stage4.md).

Actual commands in search_decimation (logs: docs/test_results/search_bp_stage4_*):

| Command / check | Result |
|---|---|
| `python -m pip install --no-build-isolation --no-deps -e .` | rebuilt project extension; current source identities |
| `python python_scripts/audit_dependencies.py` | passed; fork/patch unchanged |
| `scripts/build_dependencies.sh --check` | passed |
| `python -m pytest -q` | **299 passed, 1 skipped**, 25.93 s; 37 new Stage-4 Python tests |
| CMake Debug + CTest, assets/build/search-bp-stage4-debug | **7/7 passed** |
| CMake Debug + ASan/UBSan + CTest, assets/build/search-bp-stage4-sanitize | **7/7 passed**, detect_leaks=1 and halt_on_error=1 |
| `python tests/check_hybrid_restoration.py` | clean fork/project builds, both fork bindings, installed source identities, **7/7 native tests passed** |
| Source audit | search_bp_stage4_source_audit.json confirms unchanged TeX/fork/patch/Stage-3 algorithms and current installed project hash |
| `git diff --check` | passed |

Tests include an independent Python recursive controller using the scalar Stage-3
reference and unchanged fork BP/OSD; an independent native full-sort admission
reference; three actual recursive cycles with two retained parents and globally
four candidate executions per cycle; exact donor inheritance and R selection;
early BP/search/decimated-BP exits; retained and channel OSD inputs; successful and
invalid OSD results; reset, exception recovery and deterministic reentrancy checks.
Native assertion callbacks are a compile-time test seam, not production telemetry.
The initial focused Python test used exact equality between log(9) and the fork's
log1p(-p)-log(p) expression; its expectation was corrected to the physical convention.
The initial log is preserved. The native algorithm needed no change for that test.

Work bound: at most `max_cycles * K_run` descendant BP executions and
`T_initial + max_cycles * K_run * T_candidate` complete BP rounds. Candidate
searches have at most `M_s * B(m,q) * [1 + (max_cycles-1)*K_keep]` generated
occurrences, where B is the explicit fixed-root/refresh bound in the stage document.
At most K_keep parent plus K_run evaluated-child snapshots coexist, besides the
working session and bounded search scratch; OSD is a separate single direct call.

---

# SEARCH-BP-2.0 Stage 3: native Steps 1–4 (2026-09-22)

Implemented the native `SearchBPStage3` partial service. Initial parallel min-sum
runs in the Stage-2 ldpc session; project C++ independently checks original H/s,
uses the fork's trailing clipped mean, computes c/Q/A and exact solve/guide
scores, and emits compact hard-fixation candidates. Successful initial BP or
direct search returns immediately with the original A prediction. The full runner
remains guarded; admission, K_run/K_keep recursion and OSD fallback are not yet
implemented. No production simulation or performance/decoder advantage claim.

User-directed local-variable policy is now configurable in strict config and native
settings: `refresh_descendant` (default) refreshes the most ambiguous hypothetical
residual-unsatisfied check and its free bottom-m set; `fixed_root` retains the root
set and uses the lowest-index residual-unsatisfied check. q counts all new zero/one
fixations. Refresh mode permits q > m; fixed_root retains q <= m. Each anchored
tree deduplicates canonical patterns. Search scratch/frontiers are discarded after
each expansion and must not persist across future recursive BP cycles. The
refresh-tree count differs from N_pat(m,q), as documented explicitly.

Hypothetical ambiguity retains the parent's free-count denominator and substitutes
zero ambiguity for newly fixed variables. Only touched check probabilities are
recomputed. Physical fractional cover uses all free variables; empty minima yield
infinity and cannot expand. Candidate storage is O(Pq), scoring scratch O(N+M),
and one failed initial parent owns one Stage-2 BP snapshot. There are no per-node
BP runs, full H copies, diagnostic strings or per-iteration telemetry.

Files: five `native/search_bp_*.hpp` modules, module.cpp, native_sources.py,
CMakeLists.txt, strict config/example, focused Python/native tests, restoration
machinery and affected documentation. No fork bytes changed. Re-running the
required dependency audit retained the exact Stage-2 patch digest. Root TeX,
upstream BP/OSD, soft-hint BP and all Stage-2 fork inputs are hash-verified unchanged.
See [API, equations, bounds and traceability](docs/search_bp_stage3.md).

Actual commands in search_decimation (logs: docs/test_results/search_bp_stage3_*):

| Command / check | Result |
|---|---|
| `python python_scripts/audit_dependencies.py` | passed; fork patch unchanged |
| `python -m pip install --no-build-isolation --no-deps -e .` | project extension rebuilt; current aggregate hashes |
| `scripts/build_dependencies.sh --check` | passed |
| `python -m pytest -q` | **262 passed, 1 skipped**, 24.14 s; includes 35 new Stage-3 cases |
| CMake Debug + CTest, assets/build/search-bp-stage3-debug | **6/6 passed** |
| CMake Debug + ASan/UBSan + CTest, assets/build/search-bp-stage3-sanitize | **6/6 passed**, detect_leaks=1 and halt_on_error=1 |
| `python tests/check_hybrid_restoration.py` | clean fork/project builds, both bindings, source identities and **6/6 native tests passed** |
| `python python_scripts/validate_config.py config/search_bp.yaml.example` | passed; default refresh policy resolves explicitly |
| Source audit | search_bp_stage3_source_audit.json; TeX/fork/patch unchanged and current installed project identity verified |
| `git diff --check` | passed |

The first focused run had eight test-reference sorting failures (Python cannot
compare None and float for candidates shared by satisfied/unsatisfied roots).
The reference sort key was corrected; no native formula change was needed for
those failures. Its log is preserved as search_bp_stage3_focused_initial.log.
The intermediate focused run passed 38 tests; the final full suite also includes
the subsequent explicit refresh, fresh-state and BP-then-search success cases.
Existing upstream warning diagnostics remain in native logs; no new project
warnings or sanitizer findings were observed.

---

# SEARCH-BP-2.0 Stage 2: fork BP API (2026-09-22)

Implemented `ldpc::decimated::Session` in the opt-in fork header decimated_bp.hpp,
exported through `ldpc.hybrid_bp.DecimatedMinSumSession`. API and numerical/ownership
contracts: [docs/decimated_bp.md](docs/decimated_bp.md). The new session provides
channel reset, structural hard fixation and residual syndrome, local contradiction,
exact requested/actual/total iteration accounting, owned opaque snapshots,
continuation/restore and strict descendant inheritance, and bounded clipped LLR
history. It shares immutable precomputed adjacency and allocates reusable state
buffers once. The iteration loop performs no allocation or Python callback.

Snapshots contain q, posterior LLRs, fixed mask, original syndrome, history ring
and running sums, with compatibility/cursor/counter metadata. Logical vector
payload is 8(E + NW + 2N) + N + M bytes; graph, check-message workspace, decisions
and residuals are not copied. Ring updates are O(N) work and O(NW) space. Short
history averages actual completed samples and exposes the count; zero history
returns clipped current beliefs without adding a synthetic iteration. Descendants
retain free-edge messages/posteriors and start fresh instance history/counters.

Numerics: physical log(P0/P1), binary64 parallel min-sum, scaling in (0,1], zero
LLR ties to one, history-only L_c clipping. Extreme message additions saturate at
binary64 limits; fixed posteriors are +/-infinity and have an explicit mask. The
later project-native OSD fallback still needs a finite fixed-column reliability
policy; the unchanged OSD bridge rejects infinite input. No confidence transform,
check ranking, F_solve/F_guide, candidate selection, recursive controller or OSD
call is implemented in the new BP API. SEARCH-BP-2.0 decoder execution stays gated.

Fork files: new src_cpp/decimated_bp.hpp; updated hybrid_bp bindings.cpp,
__init__.py, __init__.pyi and source_files.py. The existing opt-in build script is
reused. The new source is covered by the transitive hash/patch/audit inventory.
Ordinary bp.hpp/osd.hpp, the old soft-hint session, OSD bridge and refined.tex are
byte-identical to their pre-stage hashes. No simulation physics or output schema
changed in Stage 2. The fork branch and upstream remote were preserved.

Actual commands in search_decimation (logs: docs/test_results/search_bp_stage2_*):

| Command/check | Outcome |
|---|---|
| `(cd external_lib/ldpc && python setup_hybrid.py build_ext --inplace)` | New fork binding built, C++17/no fast-math/no contraction |
| `python -m pytest -q tests/test_decimated_bp.py tests/test_hybrid_bp.py` | 16 passed in 0.81 s; pinned BP, scalar excluded-edge/history oracle, masks, continuation, inheritance, empty/zero/contradictory cases, ownership and boundary checks |
| `python python_scripts/audit_dependencies.py` | Regenerated required fork patch/manifest; ignored bindings and new header included |
| `python -m pip install --no-build-isolation --no-deps -e .` | Project rebuilt with refreshed transitive fork identity |
| `scripts/build_dependencies.sh --check` | Passed |
| `python -m pytest -q` | 227 passed, 1 skipped in 35.13 s, including preserved baseline regressions |
| CMake Debug + CTest, assets/build/search-bp-stage2-debug | 5/5 passed; new native test includes 360 pinned parallel min-sum comparisons |
| CMake Debug + ASan/UBSan + CTest, assets/build/search-bp-stage2-sanitize | 5/5 passed with detect_leaks=1 and halt_on_error=1 |
| `python tests/check_hybrid_restoration.py` | Patch applied to pristine upstream worktree; both opt-in bindings and project compiled without old binaries; source identities, new decimation/history transfers and 5/5 native tests passed |
| Source audit | Unchanged baseline/TeX bytes, current hashed sources and patch verified; search_bp_stage2_source_audit.json |

Native configuration used -DQEC_BUILD_TESTS=ON, Debug, the active conda Python and
pybind11 CMake directory; sanitizer configuration additionally used
-DQEC_SANITIZE=ON. All five test targets were built with -j2. Commands follow
docs/build.md. Initial focused validation recorded one incorrect test expectation:
a parallel degree-one propagation fixture converges in two rounds, not one; its
assertion was corrected. The initial log is retained. No numerical implementation
was changed to satisfy that assertion. Compiler warnings came from unchanged
upstream headers, not a changed baseline kernel.

No production simulations or new decoder orchestration were run. Full-suite
integration uses only bounded temporary existing-decoder tests. Clean restoration
reused search_decimation and other installed dependencies; no fresh conda/full
upstream build or performance claim is made. Stage-1 historical evidence and
immutable scientific snapshots remain unchanged. Remaining SEARCH-BP scoring,
admission, recursion and fallback policies are outside this stage.

---

# SEARCH-BP-2.0 architectural migration (2026-09-22)

This stage defines contracts and retires SEARCH-BP-1.0; it does **not** implement
SEARCH-BP-2.0 decoding. Root `refined.tex` is normative and unchanged. Its exact
step/equation mapping, proposed fork/project APIs, config fields and unresolved
numerical choices are in `docs/search_bp_v2_design.md`.

Native v1 implementation, project-local masked min-sum, bindings, strict template,
algorithm/14-dataset contracts, storage/analysis implementation and behavioral tests
are preserved in named `legacy/search_bp_v1` areas. `moves.txt` lists git moves;
mixed config/adapter/worker/pipeline snapshots preserve their old bytes. Legacy
config cache/output destinations are preserved. CMake/module/source hashes no
longer compile or expose SearchBPDecoder/SearchBPSettings. Generic screened/hybrid
and upstream baseline implementations remain active. No dependency kernel changed.

The reserved public kind/profile/name `search_bp` requires explicit
SEARCH-BP-2.0 and search_bp_config/3. Old versions/settings fail validation. The
contract-only template validates, but adapter/runner execution fails explicitly
before native loading, circuit work or output creation. No v1 fallback is possible.

Every new simulation now writes only config_resolved.json and one Parquet file
per condition under data/. Schema search_bp_results/1 contains shot_id,
decoder_name, logical_error, latency_ns and osd_called. Failure-inclusive wall
latency wraps the complete existing adapter boundary. OSD invocation is exact
for all current baselines, including BP-OSD zero-syndrome reuse. No raw samples,
telemetry, phase tables, schema dumps, manifests or final read-back are emitted.
The direct reader keeps conditions, decoders and execution contexts separate and
provides logical-error/Wilson, latency/tail-support and OSD-fraction summaries.
Historical wider readers are preserved; their plotting/report APIs have not been
redesigned for the new five-field schema. Use simple_search_bp for new results.

Actual commands in search_decimation:

| Command | Result |
|---|---|
| `python -m pip install --no-build-isolation --no-deps -e .` | Project extension rebuilt successfully; old native symbols absent |
| `python python_scripts/validate_config.py config/search_bp.yaml.example` | Contract validated without execution |
| `python python_scripts/audit_dependencies.py` | Audit/patch generation passed; patches unchanged, environment inventory added installed pandas |
| `scripts/build_dependencies.sh --check` | Passed |
| `python tests/check_hybrid_restoration.py` | Fresh restored source tree, both opt-in bindings and project rebuilt; 4/4 native tests passed |
| `python -m pytest -q` | Initial 215 passed, 1 skipped in 37.86 s; final 215 passed, 1 skipped in 33.33 s after OSD reuse assertions and cleanup |
| Archive/source audit | All seven native source/test moves byte-identical; mixed snapshots byte-identical; circuit/DEM/artifact/plan/identity files unchanged |
| `git diff --check` | Passed after whitespace cleanup |

New evidence: `docs/test_results/search_bp_v2_architecture_*`. Existing logs,
scientific artifacts and immutable run snapshots were not changed. Suite integration
checks use bounded temporary baseline runs, including surface/BB paired equality
across workers/warmup and five-column grouped spawn output. No production simulation
was launched. Restoration reused the existing conda environment and other installed
dependencies; this is not a new full-environment build or sanitizer acceptance.
The reduced active test count reflects retirement of v1-specific tests, not removal
of baseline numerical checks. Decoding implementation awaits the documented TeX
ambiguities: BP numerical policy, short/inherited history, empty/normalized
ambiguity, descendant branching/depth, duplicate donors/ties and full OSD LLRs.

---

# Direct benchmark plotting notebook (2026-09-22)

The local `notebook/benchmark_analysis.ipynb` now contains only explicit path/filter
settings and separate logical-error-rate and mean-decode-time plot cells. New
`analysis.benchmark_plots` reads the required Parquet columns itself and returns one
live Matplotlib figure per code family. Figures default to 3.4 x 2.55 inches and
300 dpi for a one-column figure in a two-column RevTeX paper; notebook code can edit
the returned axis before saving.

Logical error is recomputed as decoder failure OR logical mismatch, including failed
decodes without reading the stored `block_failure` field. Its shaded band is the
95% Wilson interval over physical shots. Decode-time means include failed shots.
Their shaded bands use the 95% Student-t mean interval because Wilson intervals do
not apply to continuous durations. Code family, physical error rate, distance, and
decoder ID/name/profile are exact plotting options. No telemetry, sample tables,
run merging, bootstrap, report output, or notebook summary table is involved.

The follow-up analysis adds a one-condition decode-time histogram in microseconds,
with one subplot per decoder and vertical mean/p95/p99 lines. Surface-code plots
require a distance. A pandas table indexed by code, distance, and physical rate
reports `search_bp` OSD reach from `osd_entered` and beam-decoder failures from
`syndrome_valid == False`; decoder and metric form the columns, while storage IDs
and execution metadata are omitted.

Validation in `search_decimation`: focused plotting tests passed **4/4 in 2.64 s**;
the notebook executed all **10 cells** against
`assets/runs/2026_09_22_14_04_28e7f898`; the complete project suite passed
**229 tests with 2 skipped in 24.42 s**. `git diff --check` passed. No simulation or
production sweep was launched.

---

# Grouped Parquet shot flushing and analysis-config separation (2026-09-22)

The active `search_bp` parent writer now retains the bounded per-shot producer
queue but coalesces each condition's typed columns according to the new positive
`output.parquet.shots_per_flush` setting (default 1024). Every nonempty dataset is
appended as exactly one row group per full shot group, and the final partial group
is flushed before writer close. The removed `row_group_rows` and `max_buffer_rows`
keys are rejected. Unit coverage checks independent conditions and full/final
groups; the two-worker integration check verifies four shots with
`shots_per_flush: 3` produce two row groups in both samples and decode results.

Active analysis settings now live in `analysis/config.py` and
`config/analysis.yaml.example`. Simulation `Config`, path resolution, resolved run
configuration, timing-benchmark derivation and simulation templates contain no
analysis section. The independent analysis loader rejects simulation YAML and
duplicate keys. The old `qec_bp_benchmark.config.Analysis` symbol remains solely so
the byte-preserved legacy consumers continue importing; it is not a `Config` field
and never enters simulation identity or output.

Validation in `search_decimation`: `python -m pytest -q` passed **225 tests with 2
skipped in 25.93 s**; focused grouped-writer/analysis-isolation checks passed **3/3
in 3.39 s**; and `python python_scripts/validate_config.py
config/search_bp.yaml.example` produced a resolved config with no analysis key and
only `compression`, `compression_level`, `shots_per_flush` and
`atomic_batch_commit` in its Parquet settings. No production simulation was run.

---

# Uncapped generated-node search_bp update (2026-09-22)

Removed `search.max_generated_nodes` from the active strict config, Python/native
adapter, native settings and generation loop. Search no longer freezes generation
or reports node/global-expansion-cap flags. Its expanded-node bound is solely
`max_cycles * expansions_per_cycle`; the finite Tanner graph determines the number
of children constructed by each expansion. Legacy hybrid implementations and
their historical contracts retain their original setting.

The native regression constructs 96 children in one allowed expansion (97 nodes
including the root), proving that the former 64-node template value is not an
implicit limit. Editable rebuild, config and dependency validation passed; project
tests are **221 passed, 2 skipped in 21.88 s**; Debug and ASan/UBSan CTest are both **5/5**.
The final schema-v2 bounded run `assets/runs/2026_09_22_12_42_bae00828` completed 16
shots/48 paired decodes. Its BB search generated up to 139 nodes while expanded
nodes remained at most 4 (= 2 cycles x 2 expansions); removed cap fields are absent
from the saved search-summary schema. No production sweep was launched.
Because those fields were removed, the active strict identities are now
`search_bp_config/2` and `search_bp_parquet/2`; version 1 artifacts are not
silently relabeled.

---

# Shot-streamed columnar search_bp output (2026-09-22)

The active search_bp runner no longer builds generic legacy
`results/rounds/phases` beside its typed output. Native telemetry is exported from
a const view into dataset-specific columns, without an accumulated Python
`list[dict]` or a full native telemetry copy. Each completed shot is sent to the
parent writer before its physical batch completes. Multi-worker execution uses a
bounded queue of `2*workers` shot messages and blocks producers when Parquet output
falls behind; serial execution uses the same sink synchronously. No decoder search,
cycle, beam, iteration, or event limit was added.

The Parquet schema and minimal run layout are unchanged. Each nonempty shot/dataset
chunk is now a row group. The output layer therefore retains at most one converted
shot per worker plus the bounded queue and current writer conversion, rather than
whole batch telemetry/future results. One exceptionally large shot must still fit
in native and conversion memory.

Validation in `search_decimation`: editable native rebuild passed; **220 passed,
2 skipped in 22.92 s**; two-worker spawn streaming passed; native row/column event
equality passed; Debug CTest **5/5**; focused ASan/UBSan search_bp **1/1**. Bounded
surface+BB72 smoke completed at `assets/runs/2026_09_22_12_16_a3adf726` with the
same row counts and non-timing search event data as the pre-streaming smoke. No
production sweep was launched.

The matched post-migration timing run (32 shots/condition, batch size 16, three
repeats) measured 2829.312 ms end-to-end and 1462.458 ms inside opaque decoding.
Steady non-decoding work was 578.750 ms: per-shot Parquet writes 307.676 ms,
Arrow conversion 128.585 ms, result normalization 105.056 ms, shot preparation
16.983 ms and thread-pool verification 12.022 ms. This is the intentional bounded-
memory tradeoff: output no longer accumulates to a batch, but one Parquet row group
per nonempty shot/dataset increases conversion and I/O calls. Evidence is
`assets/benchmarks/search_bp_simulation_timing_2026_09_22_streaming.json`.

---

# Simulation logic timing benchmark (2026-09-22)

Added `qec_bp_benchmark.benchmarking.simulation` and
`python_scripts/benchmark_simulation.py`. The opt-in path runs the actual worker,
typed conversion, and Parquet writer while treating each `DecoderAdapter.decode`
call as one opaque phase. Ordinary simulation runs retain their minimal output and
take no additional phase timestamps.

Bounded measurement: two conditions, 32 shots each, three decoders, batch size 16,
one worker, three repeats. Median end-to-end was **2386.514 ms** and opaque decoding
was **1516.827 ms (63.56%)**. Cached instance preparation was **571.597 ms**.
Measured steady non-decoding work was **152.694 ms**: result normalization 79.313 ms,
Arrow conversion 27.963 ms, Parquet writing 24.209 ms, thread-pool verification
11.519 ms, and shot-input preparation 3.887 ms. Physical sampling was 0.522 ms.
Evidence: `assets/benchmarks/search_bp_simulation_timing_2026_09_22.json` and
`docs/simulation_timing_benchmark.md`. No production sweep was launched.
The final project suite after adding the harness is **218 passed, 2 skipped in
21.99 s**; `git diff --check` also passed.

---

# SEARCH-BP-1.0 hard-fixation refresh (2026-09-22)

The active decoder is now `search_bp`. It has scalar
`search.expansions_per_cycle`, unified `bp.beam_width`, and per-visit
`bp.max_iteration`; the independent expansion, admission, and total-iteration
caps and every soft-hint/LLR-clip/hard-zero setting were removed. A candidate's
0/1 pattern now structurally excludes fixed columns from min-sum updates and
XORs fixed-one columns into the residual syndrome. Complete decisions restore
fixed bits before original-H validation, physical scoring, and logical prediction.

The prior HSBP-FB implementation, specifications, and templates are preserved in
`src/qec_bp_benchmark/native/legacy/`, `docs/legacy/hybrid_frontier_bp_beam/`, and
`config/legacy/hybrid/`. The current bounded template is
`config/search_bp.yaml.example`; its typed schema identity is
`search_bp_parquet/2`.

Executed in `search_decimation`:

| Check | Outcome |
|---|---|
| Editable native rebuild | passed |
| `python -m pytest -q` | **216 passed, 2 skipped in 27.19 s** |
| Debug native CMake/CTest | **5/5 passed** |
| Focused `test_search_bp` | passed; structural edge removal, residual syndrome, reduced-upstream BP equality, inheritance and beam scheduling |
| ASan/UBSan `test_search_bp` | passed with leak detection and UBSan stack traces enabled |
| `python python_scripts/validate_config.py config/search_bp.yaml.example` | passed |
| `scripts/build_dependencies.sh --check` | passed |
| bounded template run | `assets/runs/2026_09_22_11_10_a3adf726`; 16 physical shots, 48 paired decodes, minimal output layout |
| `git diff --check` | passed |

The bounded run is implementation evidence only. It is too small for decoder or
tail-performance claims, and no production sweep was launched.

---

# HSBP-FB-2.0 complete (2026-09-21; legacy)

The new `hybrid_frontier_bp_beam_ms_osd0_v2` decoder is available through shared
run/replay/analysis CLIs. It implements persistent independent Q/G search, up to W
owned BP snapshots, frozen-entry ancestor inheritance, fixed per-visit scheduling,
original-H validation, physical-cost incumbent selection and direct native CS0.
Historical profiles and readers remain available.

Strict `hsbp_fb_config/1` and the 14-table `hsbp_fb_parquet/1` output are implemented
with inventory-only loading and cross-table validation. Final checks: 290 passed/1
skipped project tests; 5/5 native Release tests; 2/2 frontier/stateful-BP ASan+UBSan
tests; clean source-only fork/project restoration passed all five native targets.
The accepted 16-shot/48-decode surface+BB72 smoke is
`assets/runs/20260921T134138.088393Z_375c9f8e3501`; replay and two-worker output are
scientifically identical. Analysis is `assets/analysis/20260921T134316.299523Z_d3d3586863`.
These are software checks, not performance evidence. See `docs/hsbp_fb_v2_migration.md`.

# Legacy configuration organization (2026-09-21)

## Saved-data analysis consumer migration (2026-09-21)

Current consumers use analysis-only `config/analysis.yaml.example`, retain strict
v1/v2 readers, and do not apply simulation execution settings. Existing full YAML
remains a validated compatibility input. The maintained notebook is the CLI default;
its kernel/checkout diagnostics cover both analysis and Config imports. Analysis
progress, configurable notebook timeout and consumer source hashes are recorded.

The complete pre-migration analysis Python implementation is byte-preserved under
`analysis/legacy/` (seven modules, snapshot hashes tested). Legacy Python/shell
consumers and notebook template remain executable in their respective legacy/
directories. Existing local notebooks, archived sources and saved scientific runs
were not rewritten. Decoder/native/dependency sources are unchanged.

The paired bootstrap now prepares integer unit totals once, keeps identical RNG
unit draws and seed/count, and guards int64 reductions with a Python-integer
fallback. Complete legacy-result parity covers shot and unequal-batch draws, nulls,
zero baseline durations, large integer totals and accuracy-margin decisions.

Actual commands in the search_decimation environment:

| Command/check | Outcome |
|---|---|
| `python -m pip install --no-build-isolation --no-deps -e .` | Passed; analysis_migration_install.log; current and legacy imports also verified from /tmp |
| `python -m pytest -q` after install and final diagnostic | **269 passed in 74.42 s**; analysis_migration_postinstall_pytest.log |
| `python -m pytest tests/test_analysis_migration.py -q` | **10 passed in 6.49 s**; analysis_migration_kernel_tests.log |
| `scripts/execute_notebook.sh config/analysis.yaml.example --run assets/runs/20260921T052534.450320Z_5d568a465320 --output assets/notebook/hybrid_20260921T052534_analysis_current.ipynb --timeout -1` | Complete; six executed code cells, 60,000 physical shots / 180,000 decoder rows; report processing **95.53 s**, bootstrap count 2,000 |
| Legacy analysis and notebook launchers on existing eight-shot accepted fixture | Both complete; analysis_migration_legacy_cli/notebook.log |
| Output/source verification and `git diff --check` | Passed; 97 report files checksummed, 12 paired groups with exact integer identities, seven preserved modules and 34 consumer source files audited |

Requested-data report: `assets/analysis/20260921T062444.686284Z_bfbbec7acc`.
Evidence and exact commands: `docs/test_results/analysis_migration_verification.json`.
The first full test invocation found one test classifying analysis-only YAML as a
simulation config (267 passed / 1 failed); its log is preserved. Corrected pre-install
suite: 268 passed in 63.76 s. The final suite includes the mixed-checkout diagnostic.
The first successful requested-data notebook is also retained separately.

Limits: full saved tables still materialize in memory. Processing times are local
consumer measurements, not decoder latency comparisons. No production simulation,
new physical samples or decoder superiority claim is involved. Existing Jupyter
sessions still need the current search_decimation kernel and a restart. See
[analysis_migration.md](docs/analysis_migration.md) for APIs, migration and legacy use.


Moved nine historical screened-reference/CS10 templates and their nine local
copies, plus local main.yaml, into config/legacy/. Decoder/rate/seed/budget settings
and comments are preserved. Relative paths were rebased and implicit path defaults
made explicit so all 17 runnable configurations resolve identically before/after;
the two production-template files remain intentionally invalid without rates.
Local YAML files remain ignored. Original local file text and relocation checks
are retained in assets/legacy_config_relocation; no scientific artifacts changed.

All existing shell and Python entry points are shared by the hybrid workflow, so
there were no legacy-only executables to move. They remain at their tested paths;
scripts/legacy/README.md and python_scripts/legacy/README.md document this boundary.
The setup script now includes config/legacy/ templates and preserves existing local
files/symlinks. Current docs/tests reference the new locations, the maintained
notebook defaults to the hybrid template, and historical commands/logs remain dated
evidence with a relocation note. No native source/build or dependency lock changed.

Validation in search_decimation:
`python -m pytest -q tests/test_config.py tests/test_hybrid_config.py tests/test_circuits.py`
passed **97 tests in 9.33 s** (docs/test_results/legacy_layout_tests.log). Checks cover
path resolution, all templates including legacy, preservation of local edits and
symlinks, unchanged scientific settings and existing circuit behavior. Git ignores
the relocated local main/smoke YAML. See legacy_layout_verification.json for counts.

---

# Hybrid migration — all six stages complete (2026-09-21)

Stage 6 finalizes the HSBP-ALG-1.0 / HSBP-EXP-1.0 implementation and its distribution.
The complete warm/cold/no-BP native service, paired v2 storage, historical v1 reader,
exact paired hypothesis analysis and saved-data consumers are implemented. Current
handoff: [docs/hybrid_acceptance.md](docs/hybrid_acceptance.md),
[docs/hybrid_native.md](docs/hybrid_native.md) and
[docs/hybrid_data.md](docs/hybrid_data.md). Historical status sections below are
preserved as dated evidence, including their then-outstanding stages.

Final review strengthened corrupt-data rejection for phase-result vocabulary,
terminal phase/stage agreement, OSD reach and prefix/OSD interval separation.
No native algorithm, circuit, DEM, logical map or dependency pin changed in Stage 6.
The source-restoration harness now checks the locked patch and every ldpc source,
rebuilds both opt-in bindings and a new project Release extension in a binary-free
isolated tree, then checks compiled/source identities and actual native decoding.
An initial harness-only identity-key error is retained in its failed log; the
corrected final restoration passed. The existing conda environment and other
installed dependencies were reused; this is not a new full-environment build.

Actual final validation in search_decimation:

| Command/check | Result and evidence under docs/test_results/ |
|---|---|
| `python -m pip install --no-build-isolation --no-deps -e .` | Built/installed the project Release extension; hybrid_stage_6_project_build.log |
| `scripts/build_dependencies.sh --check` | Passed source/runtime identities; hybrid_stage_6_dependencies.log |
| `python tests/check_hybrid_restoration.py` | Both bindings, project extension, source digests and 4/4 native tests passed; hybrid_stage_6_clean_restore_final.log |
| `python -m pytest -q` | **259 passed in 66.29 s**; hybrid_stage_6_final_pytest.log. Earlier pre-review suite: 256 passed, hybrid_stage_6_pytest.log |
| Selected pinned upstream command from docs/acceptance_report.md | **15 passed**, 6 upstream warnings; hybrid_stage_6_upstream.log |
| `python -m pytest -q tests/test_hybrid_storage.py` | 32 passed after phase-validation review; hybrid_stage_6_storage_review.log |
| Fresh CMake Release, Debug and ASan/UBSan builds + ctest | **4/4 each**; hybrid_stage_6_native_release/debug/sanitize.log |
| `python python_scripts/accept_hybrid.py --output assets/hybrid_stage_6_e2e` | Complete fresh-circuit six-case E2E acceptance; hybrid_stage_6_e2e.log and hybrid_stage_6_e2e_verification.json |
| Implementation diff whitespace check; companion-spec byte comparison | Passed. Supplied Markdown hard breaks and verbatim historical/build-log trailing spaces are preserved, so the unrestricted staged whitespace check reports those archived/input lines |

The final E2E harness executes the existing CLIs and preserves every command and
stdout/stderr under assets/hybrid_stage_6_e2e. Each case uses eight physical shots:
four surface d=3 and four BB72 R=6. Single-worker throughput, isolated latency,
two-worker throughput, replay and unprofiled replay each produce 24 paired decode
rows (hybrid, upstream CS0 and published beam). Warm/cold/no-BP ablations plus CS0
produce 32 rows. All measured base runs have 9 cycle and 26 phase rows; the ablation
run has 33 cycles and 77 phases. Unprofiled events are explicitly absent. All 12 BB
labels are verified. Single/multi/latency/replay/none scientific outputs agree
exactly with CPU caps disabled; measured scientific phase/cycle fields agree too.
The report has 12 paired groups and 65 checksummed outputs, and all six notebook
code cells execute without error. Exact integer cost identities pass. The actual
resolved manifest is [docs/examples/hybrid_manifest.json](docs/examples/hybrid_manifest.json).

Reproduce with a new directory:

```bash
conda activate search_decimation
python tests/check_hybrid_restoration.py
python -m pytest -q
python python_scripts/accept_hybrid.py --output assets/hybrid_acceptance_new
```

The production template retains surface d=5,7,9 and BB72, user-selected rates,
explicit budgets/seeds/analysis settings and optional disabled CS10. No production
sweep was launched. These smoke results establish software correctness and data
accounting, not a speed or accuracy advantage. Equal-LLR OSD ties remain platform
specific; prefix CPU caps are not full-service deadlines. Replay trials are not
independent LER observations. Optional heuristic caching/scan optimizations,
quantile-difference inference and instrumentation-overhead experiments remain
explicitly deferred. Native tests inject allocation failure safely; no actual
system-wide memory exhaustion is induced. Historical run snapshots stay immutable.

The user explicitly authorized final publication to the existing GitHub origin.
The complete migration is committed on the existing hybrid-decoder-stage1 topic
branch; main and the local ldpc screened-decimation-bp/upstream relationship are
preserved. Build products, local configs/notebooks and scientific run directories
remain ignored; reproducible source, templates, complete patches and evidence are
versioned.

---

# Hybrid migration — Stages 1–5 implemented (2026-09-21)

Stages 4 and 5 now connect the tested native hybrid to the existing paired runner,
versioned durable storage, saved-data hypothesis analysis, reports and notebook.
Work remains on the local `hybrid-decoder-stage1` branch. All prior status/log
sections below remain historical evidence; no historical scientific artifact was
rewritten. Current data/API documentation: [docs/hybrid_data.md](docs/hybrid_data.md).

Stage 4 preserves physical sampling, selected detector provenance, spawn workers,
parent-only writes, every enabled baseline on every paired shot and all 12 BB
observable labels. Native event export and truth labeling occur after the unchanged
outer service timer. Run/batch manifests are v2; tables are samples/1, decodes/2,
hybrid_rounds/1 and decoder_phases/1. The writer declares typed empty event tables
under phases and explicit omission under none. Invalid logical mismatch is null
in v2. Strict validators check pairing, event keys, counters, labels, phase order,
disjoint sums and signed residuals. Negative residuals are flagged and retained.
A BP exception may legitimately leave residual_after null. Clock/libc metadata,
model dimensions, effective settings and source/build provenance are preserved.
Historical v1 runs remain readable with validated nullable projection in memory.

Stage 5 reports stage/reach fractions, conditional valid accuracy, unconditional
block-failure contributions, cycle rescue/work/hints/caps, disjoint native costs,
paired discordance, and exact CPU/wall cost/error decomposition. Paired percentile
bootstrap supports shot or batch units with explicit seed/count/confidence. Replay
trials stay separate and cannot inflate independent LER sample size. No accuracy
margin means no equivalence/noninferiority claim. P99.9 is withheld without enough
tail support. Reports include warm/cold/no-BP comparisons, LER, CPU/wall ECDF and
survivor, stage, phase and paired-cost plots. The output-free notebook template
only consumes saved-data APIs. Local edited configs/notebooks remain untouched.

Actual validation in `search_decimation`:

| Command/check | Result / preserved log under docs/test_results/ |
|---|---|
| `python -m pytest -q` | 253 passed in 61.24 s; hybrid_stage_4_5_final_pytest.log. Earlier full run: 245 passed in 64.86 s, hybrid_stage_4_5_pytest.log |
| `python -m pytest -q tests/test_hybrid_storage.py tests/test_hybrid_analysis.py` after final event-policy guard | 49 passed in 15.37 s; hybrid_stage_4_5_final_boundary_tests.log |
| `python -m pytest -q tests/test_hybrid_analysis.py` after exact int64-before-float subtraction regression | 21 passed; hybrid_stage_5_integer_accounting_tests.log. Integer aggregate identities remain exact even above binary64's exact-integer range |
| `scripts/build_dependencies.sh --check` | Passed, hybrid_stage_4_5_dependencies.log; no native/external source changes or new native build were required in Stages 4–5 |
| `scripts/run_benchmark.sh config/hybrid_smoke.yaml.example -v` | 8 shots, 24 decodes, 9 cycles, 26 phases; hybrid_stage_4_smoke.log and *_path.txt |
| `scripts/run_benchmark.sh config/hybrid_latency.yaml.example -v` | Separate isolated one-worker run, same scientific results; hybrid_stage_4_latency.log and *_path.txt |
| `scripts/run_benchmark.sh config/hybrid_ablations.yaml.example -v` | 8 shots, 32 decodes, 33 cycles, 77 phases; hybrid_stage_4_ablations.log and *_path.txt |
| Two-worker run and replay using assets/hybrid_stage_4_configs/multi.yaml | 8 shots/24 decodes each; hybrid_stage_4_multi/replay.log and *_path.txt |
| Unprofiled replay using assets/hybrid_stage_4_configs/none.yaml | 8 shots/24 decodes; null durations and no event shards; hybrid_stage_4_none.log and *_path.txt |
| `python python_scripts/verify_benchmark.py SOURCE --compare OTHER` for multi/replay/latency/none | Every comparison: 8 samples and 24 non-timing decode results equal; phase/cycle scientific fields also equal when both measured; hybrid_stage_4_compare_*.log |
| `scripts/analyze_benchmark.sh config/hybrid_ablations.yaml.example --run ABLATION_RUN` | Complete report with 12 paired groups and 65 checksummed files; hybrid_stage_5_report.log, then final integer-accounting revision in hybrid_stage_5_final_report.log |
| `scripts/execute_notebook.sh config/hybrid_smoke.yaml.example --run SMOKE_RUN --notebook notebook/benchmark_analysis.ipynb.example --output assets/notebook/hybrid_stage_5_executed.ipynb` | All six code cells executed without error; hybrid_stage_5_notebook.log |
| `git diff --check` | Passed |

Accepted saved runs under assets/runs:

| Purpose | Directory |
|---|---|
| surface/BB throughput smoke | 20260921T044633.113050Z_465c7f27faf7 |
| isolated latency | 20260921T044637.532370Z_3e257ad8aaf3 |
| warm/cold/no-BP ablations + CS0 | 20260921T044642.224054Z_858c22c6915c |
| two workers | 20260921T044715.265104Z_681117be92f7 |
| saved-sample replay | 20260921T044722.027623Z_27e9c784f992 |
| profiling none replay | 20260921T044727.729919Z_65b8f27ea6ae |

`docs/test_results/hybrid_stage_4_5_verification.json` records paths, counts,
non-timing comparisons, all-12-BB checks, report checksums and executed-notebook
identity. The smoke hybrid visits zero syndrome, generated search goal, iterative
BP and OSD. Deterministic fixtures additionally cover transition BP, inconsistent
syndrome, invalid OSD and numerical failure, including null candidate labels and
exception accounting. Multi-table tests cover fourth-shard interruption, corrupt
or missing events, duplicate rows/foreign keys, and strict policy/version checks.
A self-contained constructed v1 fixture exercises historical false-on-invalid
labels before nullable projection; the preserved Stage 1 v1 artifact also loads.

Limits: these bounded shots validate software, not the scientific hypothesis.
No production sweep or performance/accuracy advantage is claimed. Timing trials
are not independent repeated LER evidence. A prefix CPU cap does not bound OSD or
full service latency. Bootstrap intervals are sample-dependent, and tiny/zero-event
samples are insufficient for scientific noninferiority conclusions. Optional paired
quantile-difference inference and profiling-overhead experiments are deferred.
OS allocation exhaustion is not deliberately induced by these tests. Stage 6's
full clean restoration/build and final migration acceptance remain separate work.
Later docs and boundary checks do not rewrite archived source snapshots.

---

# Hybrid migration — Stages 1–3 complete (2026-09-21)

Stages 2 and 3 are implemented on the existing local `hybrid-decoder-stage1`
branch. The pinned ldpc checkout retains `screened-decimation-bp` and its upstream
remote. Historical statuses below and their logs remain unchanged history.
The current API, ownership, numerical/telemetry conventions and implementation
limits are documented in [docs/hybrid_native.md](docs/hybrid_native.md).

Stage 2 adds the opt-in `ldpc.hybrid_bp` extension: an owned stateful parallel
min-sum session, immutable canonical graph/physical priors, finite replacement
hints, exact unclipped extrinsic arithmetic, and a direct pinned OSD-CS/order-zero
bridge. OSD receives the supplied signed LLRs and runs no BP. Ordinary upstream
BP-OSD/beam and the old reference_bp kernel are unchanged. All new sources,
including ignored bindings.cpp and the type stub, are recoverable from ldpc.patch;
the manifest, source archives and aggregate runtime/build hashes include every
authored and transitive input. Clean restoration compiled a new binding separately.

Stage 3 adds the C++ bounded correction search and complete hybrid state machine.
Search starts first, persists independent frontier/guidance heaps, uses canonical
branch partitions and the fractional residual-cover bound, and returns the first
generated goal. BP messages continue within each shot and reset between shots;
cold-BP and search-plus-OSD ablations are distinct. All paths validate original H,
predict A, and retain physical costs. Native CPU/wall summaries, per-cycle/phase
records, cap reasons and explicit numerical/resource failures are available, with
owned post-decode export. Full-recomputation reference and optimized paths preserve
exact decisions and counters. No residual-only pruning or beam truncation is used.

`DecoderAdapter(problem, Hybrid(...), profiling=True)` is callable now. Read
`DecodeResult.hybrid_summary`, then call `export_telemetry()` outside the service
timer and before another shot. Run/replay intentionally raises a precise Stage 4
storage error before creating a hybrid run: v2 schemas/events are not implemented
yet, and writing incomplete hybrid data through v1 would discard required evidence.
Existing baseline run/replay remains available. Per-node diagnostics are explicitly
unsupported; compact phase profiling is supported.

All validation below actually ran in the existing search_decimation environment:

| Command / check | Outcome and preserved log under docs/test_results/ |
|---|---|
| `(cd external_lib/ldpc && python setup_hybrid.py build_ext --inplace)` | Compiled opt-in binding; hybrid_stage_2_build.log and hybrid_stage_2_final_build.log |
| `python -m pytest -q tests/test_hybrid_bp.py` | 4 passed; independent edge-exclusion oracle, continuation/clipping, hints, empty shapes, reset; hybrid_stage_2_pytest.log |
| `g++ -std=c++17 -O2 -fno-fast-math -ffp-contract=off -I external_lib/ldpc/src_cpp tests/native/test_hybrid_bp.cpp -o /tmp/qec_test_hybrid_bp` then execute | 1,024 actual pinned CS0/OSD0 comparisons passed; hybrid_stage_2_native.log |
| `python -m pytest -q tests/test_provenance.py tests/test_hybrid_bp.py tests/test_upstream_regression.py` | 7 passed; patch restoration and 288 pristine BP-OSD comparisons included; hybrid_stage_2_regression.log |
| `python tests/check_hybrid_restoration.py` | Pristine temporary worktree + tracked patch, no old .so files, fresh opt-in compilation/digest/BP/OSD checks passed; hybrid_stage_2_clean_restore.log |
| `python -m pip install --no-build-isolation --no-deps -e .` | Recompiled/installed the project after native/CMake changes; final hybrid_stage_3_cmake_fix_build.log |
| `python -m pytest -q` | **205 passed in 50.93 s**; hybrid_stage_2_3_accepted_pytest.log |
| Focused suite after the final CMake path fix: test_config, test_hybrid_config, test_hybrid_bp, test_hybrid_search, test_hybrid_circuit_integration, test_provenance, test_decoders | **111 passed in 3.32 s**; hybrid_stage_3_cmake_fix_pytest.log |
| Release native ctest | **4/4 passed**; hybrid_stage_3_accepted_native_release.log |
| Debug native ctest | **4/4 passed**; hybrid_stage_3_accepted_native_debug.log |
| Debug + ASan/UBSan, leak detection enabled | **4/4 passed**; hybrid_stage_3_accepted_native_sanitize.log |
| `python python_scripts/audit_dependencies.py` and `scripts/build_dependencies.sh --check` | Passed after final audit metadata update; hybrid_stage_2_3_final_{audit,dependencies}.log |
| Native/source/clock identities | Verified and recorded in hybrid_stage_2_3_identities.json; native process/wall resolution reported as 1 ns on this platform |
| `git diff --check` | Passed for changed tracked files |

Native build configuration used `cmake -S . -B assets/build/hybrid-MODE
-DCMAKE_BUILD_TYPE=Release|Debug -DQEC_BUILD_TESTS=ON
-DPython_EXECUTABLE="$CONDA_PREFIX/bin/python"
-Dpybind11_DIR="$CONDA_PREFIX/lib/python3.12/site-packages/pybind11/share/cmake/pybind11"`.
The sanitize directory additionally used `-DQEC_SANITIZE=ON`. Final builds ran
`cmake --build assets/build/hybrid-MODE --target test_reference_bp test_search
test_hybrid_bp test_hybrid -j2` and `ctest --test-dir assets/build/hybrid-MODE
--output-on-failure`. Sanitizer ctest used `ASAN_OPTIONS=detect_leaks=1
UBSAN_OPTIONS=halt_on_error=1`. MODE is release, debug or sanitize; each has its
separate log and build directory. The editable extension was compiled in Release.

Stage 3 tests cover 6,912 exhaustive tiny matrix/syndrome/partial-assignment scores
and feasible-completion lower bounds, 350 independent full Python-oracle cases,
768 native reference/optimized cases, all terminal stages, zero-iteration BP
acceptance, deterministic node/time/cycle/depth limits, one-use hints, persisted
pools, cold/warm reuse, duplicate detector columns with different observables,
concurrent independent instances, numerical failure and injected allocation failure
with recovery. A bounded physical service check sampled four surface d=3 shots and
four BB72 R=6 shots at the existing software-check p=0.001, delivering every shot
to all three hybrid profiles and validating all 12 BB predictions. This was a
service test, not a v2 saved benchmark run or a logical-error performance study.

The manual fixed 80-check/180-mechanism search fixture produced 22,800 nodes across
100 trials in both paths: reference 87,122 us, optimized 38,931 us. Evidence is
hybrid_stage_3_performance.log and tests/native/benchmark_hybrid_search.cpp. This
uncontrolled-host development measurement excludes BP/OSD and is not a claim about
physical-code latency or accuracy. Further optional heuristic caching is deferred;
production currently recomputes active-column counts per node with reusable buffers.

Two intermediate issues are preserved in the logs. An initial full-suite attempt
recorded two pipeline identity failures after an adapter edit during live snapshot
runs; reruns with unchanged source passed (204, then 205 tests after counter tests).
Final incremental native rebuilding exposed four old relative CMake SHA256 paths
that failed from build directories. They now use absolute source paths; all three
incremental builds and the focused source/runtime suite passed afterward. Failed
attempt logs were retained rather than rewritten.

Remaining authorized migration stages, outside this request:

- Stage 4: carry native summaries/events through workers, compute outer service
  residuals and truth labels, implement v2 manifests/Arrow tables/atomic shards,
  preserve v1 reads and run complete paired/replay/spawn/latency workflows.
- Stage 5: paired cost/accuracy identities, bootstrap, stage analysis, reports and
  saved-data notebook execution.
- Stage 6: full fresh dependency/environment restoration and end-to-end acceptance.

No Stage 2/3 blocker remains. The new fork binding was clean-built, but no fresh
conda/full-dependency build is claimed. Upstream signed-LLR ties remain platform
specific. Prefix CPU caps do not bound OSD/full service. No production sweep,
publication or hosted fork was performed, and no scientific superiority is claimed.

---

# Hybrid migration — Stage 1 complete (2026-09-21)

Implemented on local branch `hybrid-decoder-stage1`. The historical stages 1-7
report below is preserved as history; it is not evidence of hybrid implementation.
The two supplied normative specifications are copied byte-for-byte into docs/.
See [the implementation map and decisions](docs/hybrid_migration.md).

Stage 1 adds strict nested HSBP-ALG-1.0 configuration, explicit warm, cold-BP and
search-plus-OSD profiles, finite numeric/resource validation, scalar/list budgets
resolved to explicit lists in JSON, and distinct algorithm/configuration identities.
The actual upstream `bposd_ms30_cs0` baseline is callable and correctly labeled;
CS10, screened_reference and published beam behavior remain preserved. Dispatch is
explicit and unknown kinds never fall through to beam. Enabled hybrid configurations
raise NotImplementedError before numerical imports, circuit work or run creation.
Hybrid execution is deliberately unavailable until Stage 3.

Added missing-only setup templates for hybrid smoke, ablations, user-rate production,
and runnable CS0 baseline smoke. Existing local configs/rates/sweeps/symlinks are
preserved. Production rates remain empty until supplied by the user. Provenance now
captures source .example templates, and docs define worker/model/session ownership,
non-reentrancy, shot resets, telemetry boundaries and exact future source/hash paths.
A v1/v2 mismatch-label convention difference is explicitly recorded for Stage 4.

Validation actually run in `search_decimation` (activate before these commands):

| Command | Result / evidence |
|---|---|
| `scripts/setup_local_files.sh` | Created missing local inputs; separate temporary setup tests preserved local edits and dangling symlinks across two invocations |
| `python -m pytest -q tests/test_hybrid_config.py tests/test_config.py tests/test_decoders.py` | 87 passed in 1.50 s; hybrid_stage_1_focused.log (before final label/archive/fallback additions) |
| `scripts/build_dependencies.sh --check` | Passed; hybrid_stage_1_dependencies.log |
| `python -m pip install --no-build-isolation --no-deps -e .` | Compiled/installed project extension successfully; hybrid_stage_1_build.log |
| `python -m pytest -q` | Initial 183 passed in 46.15 s; final **184 passed in 50.07 s** after review additions; hybrid_stage_1_pytest.log and hybrid_stage_1_final_pytest.log |
| `scripts/run_benchmark.sh config/bposd_cs0_smoke.yaml --verbose` | Complete isolated one-worker surface d=3 + BB72 R=6 software check; 8 shots, 24 CS0/CS10/beam rows, 4 paired batches; hybrid_stage_1_cs0_smoke.log |
| `python python_scripts/verify_benchmark.py assets/runs/20260921T031308.480482Z_694984c065d3` | Integrity validation passed; hybrid_stage_1_verification.log |
| `analysis.io.load_run` plus count/label assertions | 8 samples/24 decodes, all 12 BB observable labels; normative copies byte-identical; same verification log |
| `git diff --check` | Passed for edited tracked files; supplied normative Markdown copied without rewriting its formatting |

All new logs are in docs/test_results/. The bounded run path is also recorded in
hybrid_stage_1_cs0_path.txt. Regression coverage includes direct CS0-versus-upstream
outputs, forced BP failure followed by valid CS0, shot reuse, legacy parsing,
source archive templates, pristine ignored-binding restoration, existing complete
search/BP oracles, serial/spawn/replay pairing and analysis. No dependency source,
patch, pin or native algorithm was changed; manifest regeneration was unnecessary.
No new fresh dependency build or sanitizer run was performed in this stage.

Remaining work is intentionally outside this request:

- Stage 2: audited fork stateful min-sum and true OSD-only bridge, independent
  numerical oracles, compiled APIs, transitive hashes and clean patch restoration.
- Stage 3: native bounded search, persistent hybrid state machine, compact telemetry,
  native safety/performance checks and callable hybrid adapter.
- Stage 4: worker/event integration, CPU/wall accounting, manifest/schema v2 with
  historical v1 reading, atomic event tables and paired surface/BB/replay tests.
- Stage 5: paired cost/accuracy hypotheses, bootstrap, reports and saved-data notebook.
- Stage 6: clean restoration/build and full end-to-end/native acceptance/handoff.

No Stage 1 blocker remains. The next prerequisite is the Stage 2 fork API; there is
no hybrid kernel, OSD-only fallback or new event table yet. This smoke run validates
software only and establishes no performance advantage. No production sweep ran.

---

# Implementation status — stages 1–7 complete

Git distribution maintenance (2026-09-21): initialized the parent Git repository
on main for public publication to AKTKN/beamsearch_decimation. Working YAML and
notebooks, scientific artifacts, mutable reports, dependency checkouts and caches
are ignored. Portable .example templates and setup_local_files.sh restore missing
local inputs without replacing edits. Existing local experiments are preserved.
Native implementation and dependency sources/builds are unchanged.

Validation in search_decimation: scripts/build_dependencies.sh --check passed;
python -m pytest -q: **121 passed in 49.57 s**. Logs are
docs/test_results/git_distribution_{dependencies,pytest}.log. A temporary export
of tracked files validated setup twice, preservation of a local edit, all eight
runnable configuration templates, and the output-free notebook schema. Git
inventory checks found no working YAML/notebooks, data, binaries or gitlinks;
the authored binding remains in the locked ldpc patch. No new clean native rebuild
or production sweep was performed. Historical files were not rewritten.
The initial full-tree whitespace check flags preserved specification Markdown,
upstream patch bytes, historical logs and a reference file; those bytes are retained.

Latest maintenance: simulation and replay now accept `-v` / `--verbose`. Flushed
parent-only stderr messages show preparation, planned counts, committed-batch percent
and physical-shot totals, elapsed run time, verification and completion/failure.
Default output remains quiet; stdout remains the final run path. No YAML or scientific
parameter changes are needed. Progress updates once per committed batch, outside
per-shot decode timers. Python API: run_benchmark(..., verbose=True).

Validation: `python -m pytest -q` in search_decimation: **121 passed in 48.75 s**.
Regressions cover default quiet output, serial/spawn/replay scientific equality,
replay's actual source totals and failure progress. The command
`scripts/run_benchmark.sh config/stage5_validation.yaml --verbose` completed all four
code instances with two workers, 16 samples, 48 decode rows and eight committed
batches; verify_benchmark.py confirmed saved integrity. Evidence is in
docs/test_results/verbose_pytest.log, verbose_smoke.log and verbose_smoke_path.txt.
The clean-build acceptance results below remain historical evidence for stages 1–7.

Implemented and accepted on 21 September 2026 (Asia/Tokyo), using search_decimation.
No required stage remains unfinished, and no production sweep was run. Historical
Stage 1–3 and Stage 4–5 statuses remain under docs/test_results/.

Stages 1–5 provide physical surface d=5,7,9 and BB [[72,12,6]] Z-memory circuits,
R=d, circuit noise, verified Z-check projection and all BB logical observables;
canonical undecomposed DEMs; the opt-in forked native flooding BP; project C++ static-U
exhaustive screened search; actual unchanged BP-OSD/beam adapters; paired deterministic
serial/spawn execution, complete-service CPU/wall timing, strict Parquet, source
archives, incomplete committed subsets and saved-sample replay.

Stage 6 adds installed analysis modules for validated manifest/shard loading and
selection, summed failure components, Wilson intervals, exact descriptive timing
quantiles, ECDF/survival plots, explicit zero/tail handling, protected grouping,
checksummed reports and a successfully executed notebook. Documentation now covers
all YAML fields, schema, timing, fork maintenance, extension points and traceability.

Stage 7 built all required native dependencies and the optimized package in a new
conda prefix with independent pinned Git checkouts. The clean build exposed an ignored
authored bindings.cpp omitted from the ldpc patch. Audit/export/restoration and source
archives now preserve it; pristine-worktree byte restoration is regression-tested.
Ordinary BP-OSD and published beam kernels were not changed.

| Final verification | Outcome |
|---|---|
| Working environment `python -m pytest -q` | 117 passed in 27.82 s |
| Fresh environment `python -m pytest -q` | 117 passed in 28.52 s |
| Selected pinned upstream regressions | 15 passed; 6 expected legacy/OpenMP warnings |
| Pristine BP-OSD comparisons / complete-search oracle comparisons | 288 / 560, included in suite |
| Native Debug / ASan+UBSan | 2/2 passed each |
| Dependency/source/native import checks and pip check | Passed; all clean imports belong to the new workspace/prefix |
| Full 32-shot surface5/7/9 + BB72 smoke | 128 samples / 384 decoder rows in each of four runs |
| One/two/four-worker and isolated comparison | Exact physical samples and all shared scientific decoder outputs |
| Saved-sample replay with screened K=4 added | 128 samples / 512 decoder rows; 384 shared rows identical |
| Analysis and executed notebook | Complete PNG/PDF/JSON export; 5 notebook code cells executed |
| Production template | Expected validation failure before creating a run |

Exact argv/cwd/logs, versions, pins, native identities, run paths and comparisons are
in docs/test_results/stage_6_7_summary.json and docs/acceptance_report.md. Commands:

```bash
conda activate search_decimation
scripts/build_dependencies.sh --check
python -m pytest -q
scripts/run_benchmark.sh config/smoke.yaml
scripts/run_benchmark.sh config/latency_smoke.yaml
scripts/analyze_benchmark.sh config/smoke.yaml --run /path/to/run
scripts/replay_samples.sh /path/to/run config/decoder_sweep.yaml
scripts/execute_notebook.sh config/smoke.yaml --run /path/to/run --output assets/notebook/new.ipynb
```

Edit noise.rates or noise.sweep and decoders for user-selected experiments; sampling
and worker controls are also YAML. Outputs default to assets/runs and assets/analysis;
clean acceptance outputs are under assets/acceptance/20260920T223215Z_1c9e1644/.
The main environment remains available; the fresh prefix is preserved independently.

There is no unresolved required implementation blocker. Smoke data validate software,
not decoder superiority or extreme-tail precision. BB uses qLDPC edge coloring, not
the paper's optimized seven-layer schedule; published distance six is no circuit-distance
proof. Reference search allocates residual graphs per candidate and uses literal
exclusion operations; no latency advantage is claimed. Unavailable baseline counters
remain null. Host activity is not controlled by worker/thread settings. Exact resampling
requires the fixed environment and batch plan; stored samples support exact replay.
In-place resume and streaming/out-of-core analysis are not implemented. At the original acceptance, the root had
no Git metadata and no code or hosted fork had been published. Original specification/reference
files remain unchanged.

## Interactive analysis notebook template (2026-09-21)

Updated the local notebook/benchmark_analysis.ipynb to the current analysis API.
The first code cell contains only editable CONFIG_PATH/RUN_PATHS; subsequent cells
resolve repository-relative/absolute/home paths, diagnose stale packages, load
analysis settings and export/display verified failure/timing/hybrid/paired results.
Removed autoreload and saved outputs. The notebook selects search_decimation and
performs no simulation. The maintained CLI template and legacy notebook are unchanged.
Per user instruction, no tests or notebook execution were performed for this edit.

## Lightweight saved-data notebooks (2026-09-21)

Updated both notebook/benchmark_analysis.ipynb.example and the local editable
notebook at the user's request. Replaced create_report with separate verified
loading, failure-summary, timing-summary and configured PNG/PDF plotting cells.
Removed hybrid stage/paired tables and all bootstrap/detail-report calls. The
local CONFIG_PATH/RUN_PATHS values are preserved. Plotting reuses in-memory records
and creates a new output directory; basic summaries remain in memory. Full-report
CLI/API and historical/legacy artifacts are unchanged. Module READMEs, analysis
documentation and traceability describe the new notebook behavior.

Validation in search_decimation:
- `conda run -n search_decimation python -m pytest -q tests/test_analysis.py tests/test_analysis_migration.py`: 33 passed in 13.95s, including notebook execution.
- Executed the maintained notebook with existing bounded hybrid saved data and all
  five basic plot types: 10 PNG and 10 PDF files. Runtime guards made any report,
  hybrid stage/paired or bootstrap call fail; execution completed successfully.
- Both notebook files pass nbformat validation and code-cell compilation and
  contain no saved outputs. `git diff --check` passed.

The exact execution command, output path and current notebook source hashes are
recorded in docs/test_results/notebook_lightweight_verification.json. Execution
artifacts are under assets/notebook/lightweight_check_09a672d497/. Validation used
a small saved run, not the user's full production-size selection; no speedup is
claimed from a timed comparison. Initial integrity verification and in-memory
loading still cost time and memory. No simulations or native builds were run.

## Local notebook on-demand reads without verification (2026-09-21)

Following the user's explicit override, the local benchmark_analysis.ipynb now
loads no run data during setup. Each plot cell reads only its own decode columns
through analysis.quick_plots.plot_saved_data. Removed shared records/summaries,
checksum/provenance/pairing validation and timing-path stratification. Failure
plots sum physical-shot flags in Arrow; time plots retain every saved row with
only the selected CPU/wall clock. Existing run/config paths are preserved.
The maintained example notebook and full-report API remain unchanged in this step.

Validation in search_decimation:
- `conda run -n search_decimation python -m pytest -q tests/test_quick_plots.py`:
  3 passed in 7.40s (verified count/interval parity and required-column projection).
- Executed a copy of the local notebook on bounded existing hybrid data with
  guards forbidding validation/checksum/report/paired-analysis calls: 10 PNG and
  10 PDF files produced successfully. Exact command and source hashes are in
  docs/test_results/notebook_on_demand_verification.json; artifacts are under
  assets/notebook/on_demand_6b017c5cac/.
- `git diff --check` passed. No simulation, native changes or production sweep.

This opt-in path trusts available decode shards, including uncommitted ones, and
does not detect corrupt or duplicated records. It still reads metadata for labels
and grouping. Memory use is bounded by an instance's selected columns, plus plot
arrays; no full-size performance measurement is claimed. Updated notebook/analysis
READMEs, analysis documentation, traceability and test documentation accordingly.
## 2026-09-22 minimal simulation-output migration

The active runner now writes `YYYY_MM_DD_HH_MM_<config-hash-8>` directories with
exactly `data/` and `config_resolved.json`. Per-condition Parquet files use the
`code_distance_rounds_rate_basis_dataset` convention; e.g.
`bb72_d6_r6_p003_Z_logicalerror.parquet`. Circuit/DEM/matrix inputs remain only in
the configured cache. Run manifests, inventories, source archives, summaries,
schemas and logs are no longer emitted, and the final read-back validation pass and
manifest-based replay path have been removed from current execution.

Actual bounded checks in `search_decimation`:

- `python -m pytest -q tests/test_frontier_config.py tests/test_config.py`: 30 passed.
- Frontier surface d3 + BB72 d6 smoke: 16 shots, 48 decode rows, expected 14 typed
  files per condition, and only the two allowed top-level entries.
- Hybrid surface d3 + BB72 d6 smoke: 8 shots, 24 decode rows, four named data files
  per condition under the same two-entry layout.
- `analysis.simple_frontier` directly read the frontier smoke and returned six
  code/decoder summaries without a manifest or inventory.
- Final current suite: `python -m pytest -q` -> 218 passed, 2 skipped in 32.37 s.
  The removed tests exercised only the retired manifest/replay/report workflow;
  algorithm, circuit, native, schema, telemetry, dependency, and new result-layout
  coverage remain active.
# Current minimal-result analysis and notebook (2026-09-22)

Updated `analysis.benchmark_plots` to consume `search_bp_results/1`
`*_results.parquet` files directly, deriving exact conditions and enabled decoder
labels from `config_resolved.json`. Current public figures now cover logical-error
rate with Wilson bands, all-shot mean wall latency with Student-t bands, and
per-decoder wall-latency histograms. `decoder_event_rate_table` reports OSD-call
rates over known saved flags for every current decoder. Historical wide readers
remain as fallback. Current CPU-clock requests raise because the five-field schema
does not save CPU time.

Replaced the maintained and local benchmark notebooks with a current-layout
workflow targeting `assets/runs/2026_09_22_19_37_199b4d87`. The notebook displays
a nine-row BB72 d6 condition/decoder summary, saves logical-error, mean wall-latency
and p=.002 latency-distribution figures as PNG/PDF under
`assets/analysis/2026_09_22_19_37_199b4d87/`, and displays exact OSD-call rates.
It documents unavailable metrics and makes no decoder-advantage claim.

Focused current/historical plotting, minimal-reader and Stage-5 tests passed
39/39. The local notebook executed all six code cells without error through
`nbclient` in `search_decimation`; the environment lacks the `jupyter-nbconvert`
command. Evidence is in `docs/test_results/search_bp_current_analysis_*`.
# SEARCH-BP-2.1 search-outcome and optional-fallback migration (2026-09-23)

The active identity is now `SEARCH-BP-2.1` / `search_bp_config/4` /
`search_bp_results/2`. Native results and saved rows include exact
`correction_by_search`, true only for a valid correction constructed directly by
local combinatorial search. Initial BP, inherited descendant BP, OSD and failure
are false. Strict `osd_fallback` defaults true; false skips OSD after all BP/search
work and returns declared failure. Historical SEARCH-BP-2.0 results/1 remain
readable with the new indicator unavailable and are documented under legacy.

Validation in `search_decimation`: editable native rebuild and config dry-run
passed; focused migration tests passed 84/84; the full Python suite passed **332
tests with 1 historical-artifact skip**; native Debug and ASan/UBSan passed **7/7**
each; dependency checks and `git diff --check` passed. The maintained notebook
JSON and its legacy-results branch were checked directly. Full notebook execution
was unavailable because this environment does not provide `jupyter-nbconvert`.
