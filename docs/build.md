# Build and test

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
scripts/prepare_circuits.sh config/smoke.yaml
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
