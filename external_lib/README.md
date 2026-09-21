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
