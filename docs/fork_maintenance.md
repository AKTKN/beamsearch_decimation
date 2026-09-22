# Pinned sources and local fork maintenance

The authoritative pins/licenses/versions/source hashes/native hashes are in
external_lib/manifest.lock.json; requirements.lock.txt fixes the Python stack and
environment.conda.lock.txt fixes the Linux conda base. The workspace root has no Git
metadata, so source ZIP snapshots preserve first-party bytes. Dependency checkouts
are Git repositories; worktree .git files are supported. No hosted fork is required.

The ldpc checkout uses branch screened-decimation-bp with an upstream remote. Ordinary
src_cpp/bp.hpp, osd.hpp and upstream-compatible BP-OSD remain unchanged. The reference
kernel is opt-in through src_cpp/reference_bp.hpp, src_python/ldpc/reference_bp and
setup_reference.py. The project C++ search includes that same kernel header. The beam
baseline remains separately compiled from the pinned published source and accepts only
its five audited algorithm controls. Never replace either baseline with project BP.

After a reference kernel/build edit:

```bash
conda activate search_decimation
(cd external_lib/ldpc && python setup_reference.py build_ext --inplace)
python -m pip install --no-build-isolation -e .
python python_scripts/audit_dependencies.py
python -m pytest tests/test_bp.py tests/test_search.py tests/test_decoders.py tests/test_upstream_regression.py tests/test_provenance.py -q
```

Runtime verification hashes all four reference source/build files and the project
search/binding/CMake/header sources against the compiled identities. Rebuild and restart
after edits; identity verification is cached per process. Keep pybind11 at 2.11.1 for
Stim compatibility and avoid fast-math/FP contraction for the reference algorithm.

Upstream ldpc ignores *.cpp under src_python. The authored bindings.cpp must therefore
be explicitly included in source audits, exported patches and run archives even though
ordinary git status omits it. The clean acceptance build exposed and fixed this omission.
audit_dependencies.py now includes explicitly audited ignored sources, and the build
helper restores each missing opt-in file without overwriting existing files. The test
applies the patch to a pristine worktree and compares the actual restored bytes; a
successful git apply --check alone is insufficient evidence that a patch is complete.

scripts/build_dependencies.sh builds the pristine upstream ldpc wheel first in its own
worktree, installs the fork, builds the explicit reference extension, installs qLDPC from
its pin, compiles beam and Stim, then builds the optimized project extension. Stim's two
extensions are built sequentially because upstream shares temporary object paths.
The --check mode verifies intended imports but does not stand in for a clean build.

Keep source provenance distinct from reproducible binary identity: a different compiler,
path or build can change a native binary hash and therefore decoder ID. Do not pool those
configurations implicitly. Preserve modifications and update manifests/patches after
intentional changes; never silently move a checkout away from its pinned commit. Baseline
changes require a separately named implementation/profile with direct upstream regression
coverage. Reference modules and the original algorithm specification remain unchanged.

For hybrid_bp, setup_hybrid.py compiles only the opt-in extension. Its source_files.py
inventory includes all transitive pinned headers, bindings.cpp, __init__.py/.pyi,
itself and the build script. Extend it, the manifest/audit/restoration rules and
project hashes together when adding files. The audited patch exporter explicitly
includes ignored .cpp and .pyi sources. Run tests/check_hybrid_restoration.py after
exporting changes. The existing screened-decimation-bp branch/upstream are retained;
ordinary bp.hpp/osd.hpp behavior is not patched by this addition.

SEARCH-BP-2.0 Stage 2 adds only `decimated_bp.hpp` and symbols in the existing
opt-in hybrid binding/package. The header is a hashed SOURCE_FILES input; no
ordinary BP/OSD or old opt-in kernel changes are required. Rebuild setup_hybrid,
regenerate audit/patch/manifest, rebuild the project extension and run
check_hybrid_restoration.py. That check now executes decimation/history transfers
in the newly compiled binding and builds all five native targets. Snapshot payload
and numerical API conventions are documented in decimated_bp.md.
