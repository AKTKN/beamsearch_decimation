# Implementation status — stages 1–3 complete

Verified in the `search_decimation` conda environment on 21 September 2026.
Scope ends after Stage 3. The next unfinished stage is **Stage 4: native exhaustive
screening/search and the three decoder adapters**. No production sweep was launched.

## Delivered

- Stage 1: requested repository layout, working installable Python/C++ skeleton,
  strict YAML and independent identities, smoke/isolated-latency/sweep/production
  configurations, contracts/architecture, exact dependency and build locks. The
  algorithm specification and all six reference modules are preserved byte-for-byte.
- Stage 2: noiseless pinned surface d=5,7,9 and BB72 providers with R=d; independent
  CSS/logical-basis verification; full physical extraction and shared five-channel
  circuit noise including idle; verified Z-check measurement projection; canonical
  undecomposed DEM conversion, exact zero removal and reconstruction maps; immutable
  artifact preparation/verification/loading, fixtures and YAML launchers.
- Stage 3: explicit opt-in C++17 binary64 flooding sum-product BP inside the local
  ldpc fork, exact structural fixed-zero/one behavior, cold starts, native terminal
  posterior history/statistics, optional complete traces, status/iteration results,
  ownership and concurrent-call safety, build/source identity checks and typed wrapper.
  Ordinary upstream BP/OSD sources and the published beam kernel remain unchanged.

## Actual verification

Commands below ran with the conda environment activated. Complete logs/checksums
are preserved in `docs/test_results/` and `docs/test_results/summary.json`.

| Command / gate | Result |
|---|---|
| `python -m pytest -q` | **70 passed**, 10.74 seconds in the final source-built environment |
| Selected upstream ldpc BP/input/serial and qLDPC memory/scheduling tests | **15 passed**, six expected upstream legacy warnings |
| `tests/test_upstream_regression.py` | **288 ordinary BP-OSD outputs** equal pristine pinned build across methods, reuse and shot orders |
| `ctest --test-dir build/debug --output-on-failure` | **1/1 passed** |
| `ctest --test-dir build/sanitize --output-on-failure` | **1/1 passed**, ASan and UBSan |
| `scripts/build_dependencies.sh --check` | Intended fork, beam, qLDPC and Stim imports verified |
| `scripts/prepare_circuits.sh config/smoke.yaml` (twice) | Four real physical instances; identical paths and checksums |
| `scripts/prepare_circuits.sh config/production_template.yaml` | Expected validation failure for empty physical-rate grid |
| `git -C external_lib/pristine_ldpc_source apply --check ../patches/ldpc.patch` | Patch applies to pristine pinned worktree |
| Python compileall, shell syntax, original/reference byte comparisons | Passed |

Both ordinary native dependencies were compiled/imported before kernel integration.
The final project/reference bindings use pybind11 2.11.1. Stim v1.16.0 was compiled
from its exact pinned source, built into a wheel and installed. The unmodified ldpc
wheel is preserved and independently imported from `external_lib/pristine_ldpc/`.
Exact build commands are in `docs/build.md`; compiler logs are in `docs/test_results/`.
The build helper's check mode was exercised; a separate empty-machine acceptance run
of the complete helper belongs to Stage 7 and is not claimed here.

## Final fixtures and source identities

Use `simulation_data/stage_1_3_validation_index.json` for the four accepted final
fixtures, their source pins and all circuit/DEM/matrix/mapping hashes. BB has 72
physical data qubits, six extraction rounds, 504 measurements, 252 selected Z
check detectors and all 12 logical Z observables. Earlier development artifacts
remain unchanged and are separately identified in that index.

| Source | Pinned commit |
|---|---|
| ldpc | `d3429964cd4ffe1abfc041c6ec8b8425cb174f40` |
| BeamSearchDecoder | `084a475b05fb64308103317a1ce5a0c4b0be58aa` |
| qLDPC | `53909112b25cff8d67d1a7528501d72c5a4a34e7` |
| Stim v1.16.0 | `e2fc1eca7fd21684d433aa5f10f4504ea4860d07` |
| BivariateBicycleCodes | `fa77e3333d3ec44c79d8f914dd24c040d1da471b` |
| stimbposd | `5ed95e415be245f93d5326c4898bd0182fe8f3bd` |

Full versions, compiler/options, import paths, binary/source hashes, licenses,
local patches and wheel hashes are in `external_lib/manifest.lock.json`.
The ldpc development branch is `screened-decimation-bp`, with an `upstream` remote;
there is no hosted fork and nothing was published. The project root originally
had no Git metadata. Reference modules were located in the neighboring
`color_code_softoutput/src/color_code_softoutput/simulation/` directory.

## Limits and resolved build issues

No unresolved blocker remains for stages 1–3. The initial Stim HEAD build failed
with pybind11 3.1.0; pinning the compatible 2.11.1 toolchain and release v1.16.0
resolved it without a Stim code patch. An initial qLDPC build-tool PATH problem
was also corrected. Initial test development caught an incorrect hand-counted
DEM offset expectation and the upstream BP-OSD list-only channel argument; these
were corrected, and final tests pass.

The BB schedule is qLDPC edge coloring, not a reproduction of the original paper's
optimized seven-layer schedule. Published code distance six is not a circuit-distance
proof. The reference BP uses literal deterministic exclusion products/sums and
per-call residual allocation; no optimized O(E) iteration or latency advantage is
claimed. Priors above one half, gauge approximations and column merging are rejected.
The full screened decoder, baseline adapters, paired multiprocess runner, timing/
Parquet/replay, analysis and notebooks remain stages 4–6; final clean-build acceptance
is Stage 7. Configurations reserve those settings but do not imply those components
are already executable.
