# AF-BP-1.0 final implementation and validation report

Date: 2026-09-25. Branch: `af-bp-v1`. This report covers bounded validation of
the active four-decoder benchmark. No production Monte Carlo sweep was run, and
the smoke outcomes below are implementation evidence, not decoder-performance
or logical-error-rate estimates.

## 1. Stage commits and scope

| Stage | Commit | Scope |
| --- | --- | --- |
| Specification/Stage 0 anchor | `7e16a1b` | AF-BP TeX design and paper added to this branch |
| 1 | `9834e23` | Decimation families moved to legacy; active baselines retained |
| 2 | `90039be` | Opt-in parallel, serial and qDither fork BP engines |
| 3 | `1ade9e2` | Standalone AF-BP graph core |
| 4 | `8c1bb3f` | Native AF-BP decoder and truth-free service |
| 5 | `3a94fe8` | Relay baseline and exact iteration counters |
| 6 | `f94adad` | Four-decoder simulation, storage and analysis integration |
| 7 | This report's commit | Final validation and clean-bootstrap fixes; no scientific kernel change |

Stage 7 changed tests, validation helpers, the clean build and documentation.
The simulator circuit, DEM, sampling, truth, scheduling and timing sources have
no diff against Stage 6. Relay and the AF-BP/Beam/BP-OSD scientific kernels
were not edited.

## 2. Dependency pins and clean provenance

`external_lib/manifest.lock.json` pins ldpc
`d3429964cd4ffe1abfc041c6ec8b8425cb174f40`, Relay
`d185194ba0cb4101ced4340d82b2ee6d42f225f0`, Beam Search Decoder
`084a475b05fb64308103317a1ce5a0c4b0be58aa`, Stim
`e2fc1eca7fd21684d433aa5f10f4504ea4860d07`, and qLDPC
`53909112b25cff8d67d1a7528501d72c5a4a34e7`.
The ldpc and Beam patch SHA256 values are respectively
`e57493058fae814759928367d588b2909d378dee9f42a420249c8b7e7751cd97`
and `5e2a78ce14718e28f0d9f3a0b7c8d89e35025787bac1a51e0148cdce612bd942`;
Relay's empty patch SHA256 is
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
The ldpc AF-BP binding identifies its seven authored source inputs by digest
`37152b9831e176458d7f642571d5cdc6bc05e40836193b184d120ccde3432814`.
The project service hashes its three C++ inputs, the fork BP header and CMake.
Its working-tree compiled/source digest agreed at
`6bc7abdefc424a9903dcf4e3b4978613682799c41e2492efa10a37a6c320df9f`.

`python_scripts/clean_build.py` now applies every locked patch before building,
checks each declared source hash (including the Git-ignored AF-BP
`bindings.cpp`), restores ldpc's upstream remote, builds the three opt-in
bindings and pinned Stim, builds an independent pristine ldpc wheel for
BP-OSD regression, and compares the rebuilt source/patch identities
with the original lock. The builder excludes `.so`, wheels, object files,
build directories and circuit cache from its source snapshot. Its import and
project-service digest checks detect stale or unintended binaries. A new
interpreter verifies editable dependencies after installation because `.pth`
paths are loaded at interpreter startup; Beam's source path is installed in
the new prefix explicitly. Beam's Cython-generated C++ is regenerated from
its locked `.pyx`/`.pxd` inputs and excluded from the authored patch; the
required authored native sources are hashed. Prior failed bootstrap attempts
were preserved in their acceptance directories while these omissions were
corrected.

Final isolated active build:
`assets/acceptance/20260925T131529.418408Z_27f6592bd8` completed all
38 recorded commands from new pinned Git checkouts and a new
`search_decimation` prefix. The audit matched every dependency commit,
authored source hash and patch SHA256 to the original lock; the fork AF-BP
binding and project service digests matched their compiled identities.
Stim was built into a fresh wheel from the pinned checkout and force-installed
over the dependency bootstrap wheel. Final import locations were the new
checkouts/prefix, and `pip check` found no broken requirements. The working
environment separately passed `scripts/build_dependencies.sh --check` and
`python -m pip check`. The first clean-prefix pytest attempt passed 102 tests
and exposed one missing **test fixture**: `external_lib/pristine_ldpc` for the
288-case ordinary BP-OSD comparison. In that same clean prefix, a separate
`--no-local` clone of the exact ldpc pin had no `.so`, produced pristine wheel
SHA256 `c170eccd90e2ebe9bbbd0cc513ae0e58d237e56e4403124260954d538d0ae6ef`,
and was installed only into the test import target. The complete clean-prefix
suite then passed 103/103. The reusable builder now includes these exact
pristine-source steps. The supplemental fixture identity and test outcomes are
recorded in that acceptance directory's `pristine_restore.json`. No lock or
upstream patch bytes needed regeneration.

## 3. AF-BP architecture and mathematical equivalence

`src/af_bp_core/graph.hpp` owns one shot-local sparse Tanner graph and immutable
original H/syndrome. A factorization replaces a biclique by auxiliary `y`
and zero-syndrome defining check `q` with `y = XOR(S)`. Its sparse physical
support is the symmetric difference of the selected variable supports.
Auxiliary unary LLRs remain zero. Every physical assignment therefore has
exactly one auxiliary lift through each defining check, and that lift satisfies
the transformed graph exactly when it satisfies original H. The native test
exhaustively enumerates every physical and auxiliary assignment for the
worked nested case and 80 deterministic small random graphs after each of up
to two transforms. A separate controlled overlapping-support case verifies
the XOR cancellation rule.

`src/af_bp_core/decoder.hpp` owns H/A/probabilities, creates one mutable graph
per shot, runs the selected fork BP variant, computes physical residual and
failure weights, scores/chooses transforms, hands off bounded marginals,
validates against original H, and predicts A. It has no OSD fallback. The
Python `af_bp_service.AFBPDecoder` copies H/A/probabilities and accepts only a
syndrome; the active adapter validates original H again before recording a
correction.

## 4. Biclique, Phi and score audit

Production pair seeds, closure and deduplication agree with a brute-force
small-graph oracle for fixed examples and 160 deterministic random graphs,
tested with three different suspicious-variable sets each. Production Phi and
local `DeltaPhi_net` agree with explicit four-cycle enumeration and a
test-only full graph copy/factorization for every discovered candidate.
One-step adaptive and Shen selections also agree with exhaustive
candidate ranking on those random graphs.
The tests cover cycle removal, a new defining-check cycle, zero weighted
gain, nested transformations and overlap with rediscovery. The local scoring
path never constructs a trial graph.

The requested **negative net gain** case is mathematically impossible under
this implementation's required nonnegative weights and valid bicliques.
For selected variable set S, selected check count r >= 2 and new auxiliary
weight `w_y = max(omega over XOR support)`, each original variable weight is
the maximum over its support, hence `w_y <= sum(S weights)`. The contribution
from each selected-check pair is `pair(S) + (sum(S)-w_y)*sum(outside) >= 0`.
For each unselected check, the remaining contribution is
`(r-1)*pair(shared with S)` plus nonnegative cross terms. Thus the exact
weighted net reduction is nonnegative. A new individual cycle can be created
while the net reduction stays positive; both facts are covered. Random oracle
comparisons also assert the nonnegative bound. Producing a negative fixture
would require invalid weights or changing the specified score.

## 5. Fork BP and qDither validation

Parallel one-step edge/check/marginal output matches an independent dense
Min-Sum oracle. Serial checks compare natural and seeded random sweep order;
the oracle immediately reuses updated edge messages within the sweep. Seeded
orders reset reproducibly across shots and vary between sweeps. qDither is
checked against a separate full tiny-graph calculation of phase/chain bias,
check messages, provisional messages, random-sign-flip adjustment and
marginals. Fixed seed 1 records two nonconstant chi vectors and RSF masks,
including active and inactive mask entries. The tests verify inherited chain
posteriors, fresh seeded draws, hard caps, early stopping, history bounds and
exact phase plus chain iteration totals. The selected upstream ldpc BP suite
passed 12 tests (six existing upstream warnings).

## 6. Relay and baseline validation

Relay uses the upstream Apache-2.0/IBM-attributed source unchanged, pinned F64
`RelayDecoderF64.decode_detailed`, and single-shot calls inside each worker.
Its adapter exposes the upstream algorithm parameters and rejects
`explicit_gammas` until a reproducible array-source contract exists. Direct
upstream and adapter results agree; a contradictory case counts 2 initial plus
3 x 4 relay-leg iterations, exactly 14. Seeded adapter repeatability,
original-H validation and BB144 construction were tested. Seven selected
upstream Relay tests passed.

Beam8's counter-only patch leaves decoder decisions unchanged across 112
deterministic pristine-versus-patched fixtures: three H matrices, two prior/
budget/width settings per matrix and all corresponding syndromes. The exact
four-iteration known path exceeds the last internal `.iter`; a zero-syndrome
call resets the total to zero. Ordinary BP-OSD keeps upstream correction
behavior and reads actual `.iter`, with zero for its zero-syndrome shortcut;
OSD contributes no BP iterations. The focused baseline regressions are also
part of the full project suite, including 288 exact ordinary BP-OSD output
comparisons against a separately built pristine ldpc installation.

## 7. Legacy migration

Screened decimation, Hybrid Search/BP, SEARCH-BP and LPM-DP remain in named
`legacy/` source, config, analysis, documentation and test paths. Historical
project-native headers retained in place are excluded from active CMake and
registry paths. No active config can instantiate those families. Archived
results and scientific evidence were not edited in Stage 7.

## 8. Exact result schema and iteration accounting

Active Parquet metadata is `qec_schema=benchmark_results/2`. Each row has
exactly `shot_id`, `decoder_name`, `logical_error`, `latency_ns`, and
`total_iterations`, with structural shot/decoder keys and nonnegative int64
values. The worker reads the adapter's `total_iterations` directly; failure
rows retain spent iterations and count as logical errors. The complete-service
timer still encloses `DecoderAdapter.decode` and excludes sampling/storage.
Active plotting reads only this schema; historical schemas use legacy readers.

Synthetic expectations passed: AF-BP parallel with four graph instances
spends 1+1+1+1 = 4 iterations before declared failure; serial spends 2 on a
known transformed path; qDither spends 3 on a known phase/chain path and 5 in
the independent paper-equation oracle; Relay spends 14; Beam8 spends 4;
BP-OSD spends 1 with a maximum of 30. The storage test retains an explicit
failure's count of 9. Bounded saved BB144 rows contain exactly AF-BP 1,
Relay 2, Beam8 2 and BP-OSD 1 for their deliberately tiny configured budgets.

## 9. BB144 and worker validation

The one-round BB144 Z-memory construction has H shape `(144, 864)` with
2,952 edges and A shape `(12, 864)` with 2,132 nonzeros. All four decoders
constructed and produced one exact-schema saved row on a bounded physical
shot. A separate two-shot surface d3 acceptance ran four decoders serially
and with two workers: eight rows per run, identical shot/decoder/logical/count
values after removing latency. Pairing gave the same selected syndrome to
each decoder. Relay stochastic legs were disabled for this worker-equality
case. The test suite verifies the adapter accepts no truth input. Smoke paths
and exact observed counts are in `assets/acceptance/af_bp_stage7_smoke/result.json`.

## 10. Test and sanitizer results

| Check | Result |
| --- | --- |
| Full active Python suite | 103 passed |
| Full suite in isolated clean prefix, after pristine test-wheel restoration | 103 passed, including 288 BP-OSD reference outputs |
| Focused baseline/Relay/config/active-storage suite | 53 passed |
| Native Debug | 7 graph + 6 decoder groups passed |
| Native ASan, leak detection enabled | 7 graph + 6 decoder groups passed |
| Native UBSan, halt on error | 7 graph + 6 decoder groups passed |
| Selected upstream ldpc BP | 12 passed; six upstream warnings |
| Selected upstream Relay | 7 passed |
| Same selected upstream tests in isolated prefix | 19 passed; six ldpc warnings |
| Fresh pristine Beam versus patched | 112 identical decisions/convergence flags |
| Dependency source/import and pip check | passed |
| Clean isolated active source restoration/build | 38 recorded commands; completed and audited |
| Serial/two-worker surface + BB144 smoke | 8/8 paired non-latency rows; 4 BB144 rows |

No sanitizer failures were suppressed. The AF-BP native tests, service and
fork binding used `-fno-fast-math` and no contraction. No production sweep ran.

## 11. BB144 live-memory audit

The BB144 d12/R1 audit used a real selected-detector DEM with 864 mechanism
columns, `graph_rounds=2`, `n_fact=2` and zero BP budgets to isolate graph
work. Four factorizations were applied across three graph instances. The
whole Python process RSS was 279,666,688 bytes after circuit/DEM preparation,
279,994,368 bytes after service construction, and 280,342,528 bytes after
decode. Its 1-ms sampled decode peak was 280,150,016 bytes; process high-water
was 273,416 KiB. These values include Python, imported libraries and the
prepared circuit/DEM; RSS sampling can miss short transients and is not an
isolated C++ heap figure. The artifact is
`assets/acceptance/memory_bb144.json`.

The structural bound is current/original sparse adjacency `O(E+E0+N+M)`,
fork edge messages `O(E)`, bounded BP marginal history `O(W*N)`, and per-
factorization sparse support/selected records. Production retains a set of
adjacent check-pair seeds of `O(P)` two-int records (8-byte payload per pair
on this build), one candidate and one best candidate at a time, and
`O(n_fact)` chosen records. Trial scoring visits
affected neighborhoods and never copies full E- or N-sized graph state per
candidate. Seeds and transient candidate records are destroyed at each
factorization step; no graph-instance history is retained without diagnostic
mode. `sizeof(Biclique)=48` and `sizeof(CandidateScore)=104` bytes on this
build, excluding their bounded variable/check ID vectors and allocator
overhead. The implementation has no `O(candidates*E)` or
`O(candidates*N)` term.

## 12. Known limits

The active examples are tiny smoke workloads with intentionally short BP
budgets; they cannot support accuracy, speed or scaling claims. The Python
RSS figure is a process-level observation, not a standalone AF-BP allocation
measurement. qDither's paper mode rejects a graph handoff; graph-round use
requires the separately named `graph_warm` handoff. Relay explicit gamma
arrays lack a reproducible active-config source contract. The active minimal
run format has no in-place resume or manifest replay. The negative-net fixture
requested in Stage 7 is impossible under the specified nonnegative score, as
proved in Section 4.

## 13. Standalone extraction boundary

The movable implementation files are `src/af_bp_core/graph.hpp`,
`src/af_bp_core/decoder.hpp`, `src/af_bp_core/bindings.cpp`,
`src/af_bp_core/README.md`,
`src/qec_bp_benchmark/af_bp_service.py`, and the opt-in fork files
`external_lib/ldpc/src_cpp/af_bp.hpp`,
`external_lib/ldpc/src_python/ldpc/af_bp/bindings.cpp`, `__init__.py`,
`__init__.pyi`, `source_files.py`, `README.md`, and
`external_lib/ldpc/setup_af_bp.py`. A future standalone package should take
the AF-BP CMake target and digest inventory from `CMakeLists.txt` and
`src/qec_bp_benchmark/native_sources.py`, adapting package import paths and
build metadata. The corresponding native and fork tests move with these
files. Search through these core/binding files found no simulator runner,
Stim sampling, Parquet, plotting or truth-label dependency; the AF-BP Python
service imports NumPy, SciPy, its native binding and source-digest helper.
The active adapter, physical model and storage remain benchmark integration
code and are outside the extraction boundary.
