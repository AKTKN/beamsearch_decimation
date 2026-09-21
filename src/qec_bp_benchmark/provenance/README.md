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


Hybrid Stage 1 archives recognized source templates ending in `.yaml.example` and
`.ipynb.example` in addition to local inputs. Normative hybrid documents live under
docs/ and therefore enter the source archive. No external or native bytes changed;
future per-file runtime/build hash obligations are in docs/hybrid_migration.md.

Stages 2-3 include .pyi stubs and the native ldpc.hybrid_bp module in captured source
and binary provenance. The expanded manifest lists all opt-in/transitive sources;
project runtime checks combine HYBRID_PROJECT_FILES and fork aggregate digests.
Native source/build changes intentionally change new-run decoder identities.

Hybrid experiment metadata now records native process CPU/monotone wall clock
names and clock_getres resolutions, zero residual tolerance and libc alongside
existing Python timers/compiler/build/source evidence. Run entries preserve native
model sizes separately from physical n and record whether prefix CPU caps are
active. All storage/analysis sources enter the existing source snapshot inventory.

Stage 6 preserves an actual resolved v2 manifest example and a final E2E verification
index. Later acceptance documentation does not alter archived source bytes or run
manifests. Restored bindings and project extension verify their own embedded hashes;
the local ldpc upstream remote and development branch remain intact.
