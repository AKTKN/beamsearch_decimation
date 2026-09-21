# Source and environment capture

capture writes sources.zip plus per-file SHA256 hashes, native import paths and
binary hashes, dependency versions, compiler/flags, CPU/platform/affinity/thread
settings, clock diagnostics, and Git identities/dirty binary patches. Both .git
files (worktrees) and directories are recognized; absent metadata is explicit.
Relevant tracked and untracked Python/Cython/C++/build source bytes are archived,
including local ldpc reference sources, exact dependency locks and the original
specification/reference modules. The run retains these bytes rather than relying
only on hashes or temporary working directories. Build outputs and caches are
excluded; pinned versions and build recipe remain available for rebuilding.

Run manifests address the source archive/environment hashes; original and fully
resolved YAML/JSON are saved beside immutable artifact copies. Full per-file
artifact checksums and observable/sector/normalization maps survive cache removal.
Only relevant execution environment values are captured, not arbitrary secrets.

Stage 6–7 snapshots additionally preserve analysis/ and notebook/ sources. Explicitly
audited dependency source paths are included even when upstream Git ignores them;
this covers the authored reference bindings.cpp. The source audit exports those files
into the fork patch too. A pristine-worktree byte comparison guards clean restoration.
