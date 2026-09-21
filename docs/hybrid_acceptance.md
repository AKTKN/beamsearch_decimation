# Hybrid migration final acceptance

The implementation follows HSBP-ALG-1.0 and HSBP-EXP-1.0. The historical screened
sum-product decoder, upstream BP-OSD-CS10/CS0 and published beam remain distinct.
See [hybrid_native.md](hybrid_native.md) for algorithm/API ownership, numerical
conventions and signed-LLR tie limits; [hybrid_data.md](hybrid_data.md) specifies
all table fields, timing boundaries, event/null semantics and paired inference.

## Reproducible commands

Use the existing `search_decimation` environment. Installation from a fresh clone
uses the pinned dependency/patch workflow in [build.md](build.md). No production
rate is inferred. The production template provides surface d=5,7,9 and BB72 R=6,
with an intentionally empty rate list, all budgets and optional disabled CS10.
Supply either explicit `noise.rates` or the documented `noise.sweep`, never both.
The main fallback remains OSD-CS order zero. Warm/cold/no-BP templates are separate.

```bash
conda activate search_decimation
scripts/setup_local_files.sh
scripts/build_dependencies.sh --check
python -m pip install --no-build-isolation --no-deps -e .
python tests/check_hybrid_restoration.py
python -m pytest -q
python python_scripts/accept_hybrid.py --output assets/hybrid_acceptance_new
```

The last command creates an exclusive output directory and runs surface d=3 and
BB72 d=6/R=6 at the existing software-check rate, four shots each. It executes
single-worker throughput, isolated latency, two-worker throughput, replay,
unprofiled replay and warm/cold/no-BP ablations. All baselines decode every shot.
Fresh circuit artifacts are generated in the acceptance directory. It validates
all 12 BB labels, all declared shards and exact scientific equality across modes
without CPU caps, then executes the report CLI and maintained notebook template.
Every subprocess command/stdout/stderr and final run path is preserved. The final
verification.json records comparisons, event counts and checksummed consumer outputs.
It never overwrites an earlier acceptance directory or runs a production sweep.

`tests/check_hybrid_restoration.py` verifies the locked patch digest, restores ldpc
at its pinned commit in a new temporary worktree, and checks every locked source
hash. It rebuilds reference_bp and hybrid_bp sequentially, including both ignored
binding sources. A fresh project source copy contains no .so files; CMake builds a
Release extension and all four native tests against the restored fork. Direct
imports verify compiled/source digests and execute stateful BP, OSD0 and the hybrid.
Installed third-party dependencies are reused; this is not a new conda environment
or a full rebuild of Stim/beam. The full environment workflow remains documented
and historical evidence is preserved separately.

For standalone native Release/Debug/sanitizer validation:

```bash
cmake -S . -B assets/build/hybrid-debug-new -DCMAKE_BUILD_TYPE=Debug \
  -DQEC_BUILD_TESTS=ON -DPython_EXECUTABLE="$CONDA_PREFIX/bin/python" \
  -Dpybind11_DIR="$CONDA_PREFIX/lib/python3.12/site-packages/pybind11/share/cmake/pybind11"
cmake --build assets/build/hybrid-debug-new --target \
  test_reference_bp test_search test_hybrid_bp test_hybrid -j2
ctest --test-dir assets/build/hybrid-debug-new --output-on-failure
```

Use another directory and Release for the optimized build. For sanitizers use
Debug with `-DQEC_SANITIZE=ON` and run ctest with `ASAN_OPTIONS=detect_leaks=1`
and `UBSAN_OPTIONS=halt_on_error=1`. Sanitized timings are not benchmark results.
Stim extensions must still build sequentially with pybind11 2.11.1.

## Contract review

| Required behavior | Implementation and evidence |
|---|---|
| Search first, persistent frontier/guidance, canonical branch partition, physical bound | hybrid_search.hpp / hybrid.hpp; exhaustive Python oracle, native reference/optimized comparisons |
| Replace finite hints; unclipped extrinsic arithmetic; warm only within shot | stateful_min_sum.hpp in audited ldpc.patch; independent flooding oracle and warm/cold/reuse tests |
| Direct order-zero fallback; original H/A validity; no hidden BP | osd0_bridge.hpp / hybrid adapter; 1,024 native OSD comparisons and preserved 288 pristine BP-OSD cases |
| Truth-free paired physical inputs and all BB observables | unchanged circuit/DEM pipeline; E2E worker/replay comparisons and all-12-label checks |
| Non-overlapping phases, overlapping prefix, signed residuals | native telemetry, post-service worker export, telemetry validators and corruption fixtures |
| v1 preservation and atomic v2 complete batches | exact historical schema reader, nullable projection, four-shard interruption/corruption tests |
| Exact paired speed/accuracy accounting and context separation | analysis.hybrid integer identities, conditional denominators, counterexamples, shot/batch bootstrap and replay tests |
| Saved-data-only report/notebook and complete provenance | accept_hybrid.py consumer execution, checksums, resolved manifest example and archived source/build identities |

The final review strengthened storage validation for enumerated phase results,
terminal-phase correspondence, OSD reach and prefix/OSD interval separation. This
changes corruption detection, not the decoding algorithm. The first expanded
restoration harness completed compilation but referenced incorrect identity key
names; its preserved initial log records that harness failure. The corrected
harness verifies the actual project_sha256/fork_sha256 interface and passes.

## Limits

A first-valid correction is not a minimum-cost or logical-correctness certificate.
OSD uses pinned signed-LLR ordering, including platform-dependent equal-value ties.
Prefix CPU limits do not bound OSD/full service latency. No production rate sweep,
advantage in LER or latency, or accurate extreme-tail estimate is claimed by these
smoke checks. Bootstrap intervals depend on observed pairs; a predeclared margin
is required for the reported noninferiority criterion. Replayed shots never count
as independent LER evidence. Full analysis tables are materialized in memory.

Optional cross-node heuristic caching, proven minimum-scan early exits, paired
quantile-difference inference and instrumentation-overhead experiments remain
explicitly deferred. Actual OS-wide memory exhaustion is not induced; native tests
inject allocation failure and check safe recovery. There are no placeholders on
required decoder, data, replay or saved-data analysis paths.

Actual final commands, outcomes and artifact paths are indexed in STATUS.md and
`docs/test_results/hybrid_stage_6_*`. Earlier acceptance logs remain historical.
