# LPM-DP-BP-1.0 final implementation report

This report closes the validation and maintainability stage for the decoder
specified by the repository-root `local_parity_decimation_note.tex`. It records
bounded software validation only. No production Monte Carlo sweep was run, and no
accuracy, latency or memory advantage over Beam Search is claimed.

## Identity and stage history

The final identity is kind `lpm_dp_bp`, profile/name `lpm_dp_bp_v1`, algorithm
version `LPM-DP-BP-1.0`, config schema `lpm_dp_config/1` and result schema
`lpm_dp_results/1`. The branch is `search-bp-lpmdp-v1`.

| Stage | Commit | Scope |
|---|---|---|
| 0 | audit-only baseline `1f2a609` | Read-only note, SEARCH-BP, fork, simulator and memory audit; the audit did not create a separate code commit |
| 1 | `7e81209` | Standalone exact LPM-DP candidate generator |
| 2 | `b49befa` | Exact final check-to-variable messages in fork snapshots |
| 3 | `2821b00` | Complete bounded native decoder state machine |
| 4 | `2f3a355` | Strict config, one-call adapter and minimal simulator results |
| 5 | final commit | Clean-build correction, final validation, deterministic worker check and documentation |

Across Stages 1--4 the new project files are `lpm_dp_model.hpp`,
`lpm_dp_candidates.hpp`, `lpm_dp_decoder.hpp`, `lpm_dp_bindings.hpp`,
`test_lpm_dp.cpp`, `test_lpm_dp_decoder.cpp`, `test_lpm_dp_stage4.py`, the bounded
config example and the four stage reports. Existing files changed by those stages
are `CMakeLists.txt`, native source inventory/registration, config and adapter,
minimal storage/runner routing, analysis readers, fork patch/manifest, exact-BP
tests and the relevant READMEs/status/traceability documents. Stage 5 changes are
limited to clean-build restoration, tests and documentation; it changes no
scientific C++ or simulator logic.

The final branch-level file inventory is:

- native/build: `CMakeLists.txt`, `src/qec_bp_benchmark/native/{README.md,
  lpm_dp_model.hpp,lpm_dp_candidates.hpp,lpm_dp_decoder.hpp,
  lpm_dp_bindings.hpp,module.cpp}`, `src/qec_bp_benchmark/native_sources.py`;
- fork/audit: `external_lib/{README.md,manifest.lock.json,patches/ldpc.patch}` and,
  in the patched fork, `src_cpp/decimated_bp.hpp`,
  `src_python/ldpc/hybrid_bp/{bindings.cpp,__init__.pyi}`;
- Python integration: `src/qec_bp_benchmark/{config.py,decoders/__init__.py,
  README.md}`, `runner/{README.md,pipeline.py,worker.py}`,
  `storage/{README.md,minimal.py,results.py}`,
  `analysis/{plots.py,simple_search_bp.py}`;
- configuration: `config/{README.md,lpm_dp.yaml.example}`;
- tests/build maintenance: `python_scripts/build_dependencies.py`,
  `requirements.lock.txt`,
  `tests/{README.md,check_hybrid_restoration.py,test_decimated_bp.py,
  test_hybrid_config.py,test_lpm_dp_stage4.py,test_provenance.py}` and
  `tests/native/{README.md,test_decimated_bp.cpp,test_lpm_dp.cpp,
  test_lpm_dp_decoder.cpp}`;
- documentation/status: `AGENTS.md`, `README.md`, `STATUS.md`,
  `docs/{README.md,build.md,configuration.md,data_dictionary.md,decimated_bp.md,
  lpm_dp_stage1.md,lpm_dp_stage2.md,lpm_dp_stage3.md,lpm_dp_stage4.md,
  lpm_dp_final_report.md,simulation_output.md,traceability.md}`.

## Final architecture and call graph

Responsibilities remain separated:

- `lpm_dp_model.hpp` owns settings and typed local/DP records;
- `lpm_dp_candidates.hpp` owns parent summarization, region selection, cavity
  fields, joint one/two-check sum-product, exact list DP, retained mass and
  adaptive fixation count;
- fork `decimated_bp.hpp` owns parallel min-sum, exact hard masking, warm
  inheritance, bounded history and opaque snapshots;
- `lpm_dp_decoder.hpp` owns root/child scheduling, original-`H/s` validation,
  deterministic online beam retention and one-time optional OSD-0;
- `lpm_dp_bindings.hpp` exposes settings, a compact result and one native
  `decode(syndrome)` call;
- Python parses strict configuration, constructs the native object once per
  worker, invokes it once per shot, independently validates the result and hands
  it to the existing simulator label/storage path.

The scientific path is exactly:

```
channel BP
-> per-parent LPM-DP local candidate generation
-> one structural hard-fixation pattern
-> warm-started child BP
-> original H/s validation
-> bounded post-BP retention
-> repeat for at most max_cycles
-> optional one-time OSD-0 fallback
```

The LPM-DP headers do not include SEARCH-BP search/admission headers. The path has
no `LocalSearch`, `f_solve`, fractional solution search, `f_guide`, ambiguity-gain
search, solve/guide quotas, cross-parent pre-BP admission, Tesseract/A*, unbounded
frontier or assignment enumeration. Candidate generation is polynomial list DP
with at most four parity states and width `candidates_per_parent`; it returns
decimation patterns, never complete search corrections.

All ownership is RAII (`vector`, `shared_ptr`, `unique_ptr`), with no raw owning
pointers or hidden mutable static state. `DecoderSettings::validate()` and
`Settings::validate()` centralize parameter checks. Canonical IDs, local costs,
full fixation patterns and monotone child IDs define every tie. The decoder object
is explicitly non-reentrant and worker-owned. No accidental dead scientific code
was found or removed.

## Configuration and behavior

| Parameter | Default | Parameter | Default |
|---|---:|---|---:|
| `history_window` | 8 | `history_clip` | 25.0 |
| `pool_size` | 32 | `local_check_limit` | 2 |
| `max_fixations` | 4 | `candidates_per_parent` | 2 |
| `retained_mass_target` | 0.9 | `proposal_clip` | 30.0 |
| `initial_iterations` | 30 | `candidate_iterations` | 20 |
| `retained_parents` | 8 | `max_cycles` | 10 |
| `scaling_factor` | 1.0 | `osd_fallback` | false |

Unknown and obsolete SEARCH-BP fields are rejected. Each parent independently
generates at most `candidates_per_parent` patterns; local probabilities are never
compared across parents. Fixed zero removes its column, fixed one also toggles the
original column in the residual, both message directions on fixed edges are zero,
and the free edges inherit the parent messages. Child history is reset before BP.
Every returned correction, including OSD output, is checked against original
`H/s`. Bounded exhaustion is a declared failure unless fallback is enabled. OSD is
then called exactly once, and `osd_called` is the native invocation flag.

## Fork and Python boundary

Stage 2 made the minimum fork change required by the note. The completed BP round
already computed exact edge-aligned check-to-variable messages in its check
workspace. That existing array now belongs to `Snapshot`; iteration writes the
same buffer used for posterior/extrinsic updates, and restore copies it without a
new update or posterior-subtraction approximation. Descendant construction zeros
both directions only on fixed columns. The fork files are
`src_cpp/decimated_bp.hpp`, `src_python/ldpc/hybrid_bp/bindings.cpp` and
`src_python/ldpc/hybrid_bp/__init__.pyi`, represented by the tracked ldpc patch and
manifest. BP equations, stopping, decisions, ordinary BP/BP-OSD and existing
decoder controllers did not change.

No Python candidate, ranking, beam-cycle, child-BP or fallback-control loop exists.
The adapter signature contains only `syndrome`; logical truth remains exclusively
in the worker after the complete decoder-service timer.

## Simulator and saved results

Circuit construction, DEM conversion, noise, physical sampling, selected-sector
projection, syndrome/truth generation, seed derivation, scheduling and logical
comparison are unchanged. LPM-DP uses the existing timer around the entire
adapter service: input copying, initial BP, candidate/child cycles, retention,
optional OSD, correction validation, prediction and cost are included. Sampling,
truth comparison and Parquet I/O are excluded.

The exact non-null saved fields are `shot_id`, `decoder_name`, `logical_error`,
`latency_ns` and `osd_called`. No checks, variables, q, retained mass, local costs,
cycle/candidate counts, BP history or search telemetry are saved. Declared failure
sets `logical_error=true` without inventing a correction. A final simulator-core
diff over circuits, artifacts/DEM, noise, `runner/plan.py` and physical simulation
is empty; Stage-4 runner/storage edits only route the selected minimal schema.

## Bounded memory

For `N` variables, `M` checks, `E` Tanner edges, history window `W`, fixation depth
`D` and retained width `B`, the exact logical vector payloads are

```
S = 8(2E + NW + 2N) + N + M        snapshot
P(D) = S + 8D                       retained parent plus canonical pairs
Q = S + N + M                       reusable session, including decision/residual
```

At cycle `c`, old depth is at most `c*q_max` and child depth at most
`(c+1)*q_max`. The conservative live decoder core is

```
B*P(c*q_max) + B*P((c+1)*q_max) + Q
+ 8N mean + 8(c+1)q_max temporary pattern
+ one-parent candidate-generator scratch + O(K*q_max) result metadata.
```

The two `B` terms are a rigorously bounded generational alternative to one
temporary child snapshot: exact global post-BP top-`B` retention requires the old
generation while up to `B` competitive children are accumulated online. A child
is snapshotted only if competitive; when full, the worst child snapshot is
destroyed before its replacement is captured. The reusable session is the only
full temporary child state. Old parents are released before the next cycle.

The shared flattened graph payload is `16E + 24N + 8M + 16` bytes on the validated
64-bit ABI, plus observable rows and bounded upstream OSD structures. Candidate
scratch is
`O(N+M+pool_size*d_v^2+|V_A|+S_state*K*q_max)`, with `S_state<=4`; only one
parent's scratch and `O(K*q_max)` returned metadata are live. History is exactly
`NW`. There is no `raw_candidate_count*N`, `raw_candidate_count*E`, unbounded
frontier or exponential assignment store.

For BB72 d6/r6 (`M=252,N=2232,E=7776`) and reference defaults, the final-cycle
core vector bound is 5,218,344 bytes; including validated ABI inline state/session
and temporary objects gives 5,223,048 bytes, before graph, OSD and allocator
overhead.

The representative native decoder fixture exercises multiple cycles and reaches
its configured maximum of two old parents and two retained children. Its exact
logical vector-payload bound is 1,896 bytes. `/usr/bin/time -v` measured a 4,436
KiB process peak RSS; that process value deliberately includes the C++ runtime,
allocator, graph, OSD object and test harness and is not presented as a snapshot
measurement.

## Determinism and validation evidence

All commands ran in `search_decimation`; no production simulation was launched.

| Check | Final result |
|---|---|
| Isolated clean build | `assets/acceptance/20260923T062443.251415Z_77b03b3e46`: complete in a new conda prefix and new pinned checkouts, with no copied binary, wheel, build directory or circuit cache |
| Dependency, fork and source identities | Checks passed; ldpc upstream is `d3429964cd4ffe1abfc041c6ec8b8425cb174f40`, fork source is `b09388ad30027ddbcc71826990b9106be9f124ac1abdf54f905d76492a6d9488`, project source is `4472898f7dd837a9418826f82b2d316892fbd45c3dc4bf87526b9a53f659d953`, and the native build declares C++17/binary64/no-fast-math |
| Complete project pytest | 337 passed, 1 skipped in 44.01 s in the working environment and again in 33.53 s in the isolated clean prefix; the skip is an unavailable historical artifact |
| LPM-DP/fork/old-decoder focused regression selection | 128 passed in 15.67 s, including all 288 pristine/fork BP-OSD comparisons |
| Selected upstream ldpc BP suite | 12 passed; six existing OpenMP/legacy warnings |
| Fresh native Debug CTest | 9/9 passed |
| Fresh ASan/UBSan CTest | 9/9 passed with leak detection and halt-on-error |
| Pristine-fork restoration and project rebuild | source/build identities passed and native CTest 9/9 passed |
| Serial/spawn simulator smoke | one-worker and two-worker Surface-d3 runs had exactly equal non-latency rows, including `osd_called`, for LPM-DP, Beam Search and BP-OSD |
| Representative memory workload | exact payload bound 1,896 bytes; process peak RSS 4,436 KiB |

The clean-build audit found two bootstrap defects outside the scientific path. The
explicit pristine-fork restoration list omitted the already required
`src_cpp/decimated_bp.hpp`, and `pyproject.toml`'s pandas dependency was absent
from `requirements.lock.txt`. The restoration inventory now includes the header,
a provenance test derives and checks all untracked hybrid source inputs, and
pandas 3.0.6 is locked. These corrections change neither decoder equations nor
simulator behavior.

The formerly failing recursive config-template test also now classifies the
preserved `config/legacy/search_bp_v2/` templates as legacy expected-invalid
inputs, just as it already did for SEARCH-BP-v1. This is a test-discovery
correction only; current and historical config parsers were not changed.

The active minimal runner intentionally does not retain physical samples and
rejects manifest replay as legacy-only. Therefore replay was not claimed or
simulated. One-worker serial and two-worker spawn runs use the same deterministic
sample plan and are compared after removing only `latency_ns`.

## Limitations and risks

- The bounded decoder may declare failure; OSD fallback is off by default.
- A locally infeasible/contradictory selected region does not trigger an unbounded
  search for alternative regions or candidates.
- Running-sum history uses the documented session addition order. It is
  mathematically the clipped mean but is not claimed bitwise equal to a different
  resummation order.
- Candidate retained mass is the probability covered inside the selected local
  parity model before structural rejection and post-BP beam retention. It is not
  a posterior probability that a pattern is globally correct, not a decoder
  success probability, and cannot be multiplied across cycles as one.
- The main-body retention score is a heuristic, not a success probability. Exact
  performance and tail behavior require separately designed production studies.
- Measured RSS includes runtime, allocator, graph, OSD and test harness. It is not
  a per-snapshot measurement. Upstream OSD internal capacities are bounded by the
  model but not included in the exact core byte formula.
- The decoder is non-reentrant per object. Parallel execution uses independent
  worker-owned instances.
- Current replay is unavailable under the deliberately minimal output contract.

## Appendix scoring assessment and future ablation

The implemented main-body retention metric does have deletion bias when `q`
varies. If removed variables are less confident than the parent mean, the mean
over remaining free variables increases even when their beliefs do not change,
exactly as the note's appendix equation shows.

The proposed correction is implementable with one inherited scalar debt per
parent and `O(N)` work: add the parent uncertainties of newly fixed variables to
the debt, then score the child by debt plus the sum of its remaining uncertainty,
divided by fixed global `N`. It adds one scalar per retained state and one bounded
linear pass; it preserves all memory bounds and introduces no candidate-times-`N`
or candidate-times-`E` storage.

It is deliberately absent from `LPM-DP-BP-1.0`. It changes the meaning and ordering
of post-BP retention and may penalize correct branches that require many
fixations. It should be evaluated later as a separately named/versioned, paired
ablation, not silently folded into the reference decoder. Other future ablations
should likewise isolate one change at a time, for example alternate local-check
selection or fallback policy, without using smoke results as evidence of
superiority.
