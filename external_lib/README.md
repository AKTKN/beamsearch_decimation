# external_lib

Pinned source checkouts retain original documentation/licenses. manifest.lock.json and docs/dependency_audit.md record integration. ldpc is a local development branch; beam remains a separate baseline. wheels/pristine_ldpc preserve the unmodified reference build.

See ../docs/fork_maintenance.md for restoration, auditing and rebuild instructions.
The exported ldpc patch explicitly includes the authored bindings.cpp ignored by
upstream Git rules; the audit and provenance archive must preserve it. Fresh-build
evidence and exact module identities are in ../docs/acceptance_report.md and
../docs/test_results/stage_7_dependency_manifest.json. Never copy the main build's
binaries into a claimed clean acceptance environment or retune published kernels.

Git distribution includes the manifest and patches, not nested dependency Git
repositories, native binaries or wheels. scripts/build_dependencies.sh restores
missing pinned checkouts and the local ldpc fork. Existing checkouts remain intact.


Hybrid Stage 1 does not patch the fork or change dependency/native hashes. The new
CS0 profile calls existing upstream BP-OSD with order zero. The future stateful
min-sum and OSD-only interface, exact planned authored paths and transitive hash
coverage are documented in docs/hybrid_migration.md; they are Stage 2 work.

Stages 2-3 now add ldpc.hybrid_bp: owned stateful parallel min-sum and direct pinned
OSD-CS/order-zero, preserving upstream and reference_bp source/API behavior. Build
with setup_hybrid.py, then audit and rebuild the project. source_files.SOURCE_FILES
covers transitive native headers, binding, shim, type stub and build recipe. The
tracked patch includes ignored bindings.cpp. tests/check_hybrid_restoration.py
compiles a pristine patched worktree independently; test_provenance verifies every
listed source byte. See docs/hybrid_native.md and STATUS.md.

Final hybrid restoration is exercised by tests/check_hybrid_restoration.py: all
locked ldpc source hashes must match the pin plus patch before either opt-in binding
is rebuilt. The fresh project extension/native tests consume that restored source.
The local fork branch/upstream remote remain unchanged; GitHub distribution carries
the pinned manifest and complete patch, not ignored dependency working directories.
