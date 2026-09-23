# Build and test

The final SEARCH-BP-2.0 audit is in search_bp_implementation.md. After project
search header edits, rebuild the editable extension; the fork is unchanged in
this pass. Current native builds use all nine test targets below, including under
ASan/UBSan (detect_leaks=1, halt_on_error=1); the standalone decoder microbenchmark
is separately compiled without sanitizers. Logs are `test_results/search_bp_final_*`.

SEARCH-BP-2.0 Stage 4 compiles the full native decoder and `test_search_bp_stage4`;
Stage 5 integrates the simulator without changing native sources. See search_bp_stage4.md. Stage 3 supplies
the reusable partial service and `test_search_bp_stage3`.
Stage 2 adds the fork BP test target `test_decimated_bp` and opt-in
DecimatedMinSumSession binding. See decimated_bp.md. The old
headers/bindings are archived and excluded. Existing screened and hybrid native
targets retain C++17, no fast-math and no contraction. After a watched ldpc hybrid
source changes, rebuild its opt-in extension, audit dependencies, then reinstall
the project editable. `native_sources.py` lists the active project hash inputs.
`python tests/check_hybrid_restoration.py` rebuilds both opt-in bindings and the
nine active native test targets from restored sources in an isolated directory.

Create the locked environment and build every required native dependency from its
pinned checkout. The helper also installs the optimized project extension and
the independent pristine BP-OSD reference used by regression tests:

```bash
conda create -n search_decimation --file environment.conda.lock.txt
conda activate search_decimation
scripts/build_dependencies.sh
python python_scripts/audit_dependencies.py
scripts/build_dependencies.sh --check
python -m pip check
python -m pytest -q
```

Skip environment creation when using the existing search_decimation environment.
The pristine ldpc wheel is built from an independent pinned worktree before applying
the reference-kernel patch to the main checkout.
Its content hash is recorded in the manifest. A beam_search_baseline.pth in the
conda site-packages points to the external decoder directory; the bootstrap script
will install this path. Sources/patch restore and native debug commands are recorded
as they are introduced. Optimized builds must not enable fast-math.

Opt-in reference kernel and focused native tests:

```bash
(cd external_lib/ldpc && python setup_reference.py build_ext --inplace)
cmake -S . -B build/debug -DQEC_BUILD_TESTS=ON -DCMAKE_BUILD_TYPE=Debug -Dpybind11_DIR="$(python -m pybind11 --cmakedir)"
cmake --build build/debug -j2
ctest --test-dir build/debug --output-on-failure
cmake -S . -B build/sanitize -DQEC_BUILD_TESTS=ON -DQEC_SANITIZE=ON -DCMAKE_BUILD_TYPE=Debug -Dpybind11_DIR="$(python -m pybind11 --cmakedir)"
cmake --build build/sanitize --target test_reference_bp test_search -j2
ctest --test-dir build/sanitize --output-on-failure
scripts/prepare_circuits.sh config/legacy/smoke.yaml
```

The reference extension uses -O3, C++17, -fno-fast-math, -ffp-contract=off. Native
debug tests retain assertions even when built under an optimized configuration.
ASan/UBSan are applied to the standalone kernel and search tests. Do not benchmark sanitized
builds. Stim requires pybind11~=2.11.1; this environment pins 2.11.1 for all bindings.
Build Stim extensions sequentially: upstream extensions share temporary object paths,
so setuptools build_ext -j is not used. Pinned Stim release is v1.16.0.

For a fresh installation, `conda create -n search_decimation --file environment.conda.lock.txt`
recreates the Linux conda base, followed by `scripts/build_dependencies.sh`. The build
helper checks exact checkout commits, preserves existing local changes, creates a
pristine ldpc worktree if its wheel is absent, applies the recorded opt-in patch only
when absent, and installs the beam import path. `scripts/build_dependencies.sh --check`
is a short verification command. The full helper and its check mode were executed
in the final fresh environment; acceptance_report.md records exact evidence.

## Clean acceptance

The build helper has now been exercised in a new conda prefix and independent pinned
Git checkouts, without old native binaries/wheels/build directories or circuit cache.
Acceptance paths, commands, results and the initially discovered patch omission are
recorded in acceptance_report.md. Numerical third-party packages use the locked
conda/Python distributions; the project's native extension, ordinary/pristine ldpc,
reference binding, published beam and Stim are compiled from their pinned sources.
qLDPC is installed from its pinned source checkout. Reference-only BB/stimbposd
checkouts are retained without claiming an executed replacement decoder.

The reusable clean-build wrapper creates a timestamped source snapshot/environment:

```bash
conda activate search_decimation
scripts/clean_build.sh assets/acceptance
# Activate the printed build's envs/search_decimation prefix, then cd to workspace/.
python -m pytest -q
```

It records all commands, logs and exceptions and preserves the current workspace.
The environment basename remains search_decimation, including when created at a
custom prefix. Source clones can use the existing local Git object database as a
transport with --no-local; checked-out files still come from locked commits and no
compiled products are copied. The conda executable may be supplied with --conda.
PIP_NO_CACHE_DIR and PYTHONNOUSERSITE are set, and PYTHONPATH is cleared. Stim's source
build is deliberately sequential and can take several minutes. Installation itself
does not launch a production simulation.

The opt-in patch must contain ignored authored bindings.cpp. The updated audit and
restoration helper include it; test_provenance applies the complete patch to a pristine
worktree and compares bytes. This fixes the missing-source defect exposed by the fresh
build, while leaving all ordinary upstream algorithms unchanged.

Notebook dependencies are pinned in requirements.lock.txt and in the `notebook`
optional project extra. Headless tests/exports use MPLBACKEND=Agg. Entry points for
analysis, notebook execution and verification are documented in analysis.md.

## Hybrid Stages 2-3 builds

Activate search_decimation. Build the opt-in fork with `(cd external_lib/ldpc &&
python setup_hybrid.py build_ext --inplace)`, regenerate audit/patch/manifest with
`python python_scripts/audit_dependencies.py`, then rebuild the editable project.
`python tests/check_hybrid_restoration.py` restores the pin/patch in an independent
temporary worktree and compiles its binding without existing native binaries.
CMake QEC_BUILD_TESTS now includes test_hybrid_bp and test_hybrid; QEC_SANITIZE applies
ASan/UBSan to these too. Hybrid build hashes use absolute paths and watched inputs
so automatic reconfiguration works from the build directory. See hybrid_native.md
and STATUS.md for exact commands/results; no full fresh-environment claim is made.

## Hybrid final restoration and E2E

The expanded `python tests/check_hybrid_restoration.py` now builds both reference_bp
and hybrid_bp from the locked patch and a new project Release extension against that
restored fork, then runs all four native tests and checks compiled/source digests.
No previous native binaries are copied. Other installed conda dependencies remain
in use. `python python_scripts/accept_hybrid.py --output NEW_DIRECTORY` performs the
bounded fresh-circuit E2E workflow, including saved-data consumers. See
[hybrid_acceptance.md](hybrid_acceptance.md) for commands, scope and limitations.
