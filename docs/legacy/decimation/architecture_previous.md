# Architecture and interfaces

`qec_bp_benchmark.config` parses strict safe YAML before numerical imports. Frozen
models reject unsupported profiles/parameters and expand physical sweeps. Paths are
relative to the YAML. `identity` hashes independent scientific, decoder, sampling
and run records with canonical finite JSON, without rounded display identities.

`circuits` (Stage 2) provides noiseless templates, verified measurement provenance,
selected views, BB algebra validation, the common noise profile and inventories.
`dem` converts undecomposed Stim instructions into canonical sparse H (checks by
mechanisms), sparse A (logical observables by mechanisms), binary64 priors and
normalization maps. `artifacts` persists exact bytes and deterministic hashes.
The preparation CLI takes YAML only; no decoder or production simulation runs there.

`ldpc.reference_bp` (Stage 3) exposes a separately compiled opt-in C++ flooding
kernel in the pinned fork. It owns its graph/prior copies, uses per-call mutable
buffers and native history, and returns status/iterations/correction/beliefs/traces.
`qec_bp_benchmark.bp` validates the intended fork identity and provides a typed thin
interface. No production Python BP or search loop is permitted. Project `_native`
contains the independently authored C++ exhaustive search using that same kernel.

The decoder/search, paired runner and importable analysis components are described
below. Clean-build acceptance evidence is recorded in acceptance_report.md.

Tests contain independent scalar/GF(2) expectations and controlled fault fixtures.
External sources remain separately licensed and pinned; local patches and source
identities are preserved under external_lib. Reference modules are examples only.

## Stages 4–5 implementation

`native/search.hpp` now uses the Stage 3 C++ ReferenceBp class directly for initial
and all candidate runs. Its thin pybind module exposes typed results, score/pool
inspection for tests and embedded source hashes. `decoders` verifies the build,
constructs the three actual native backends and provides one complete truth-free
per-shot service with correction/prediction/status/cost/counters/diagnostics.

`runner.plan` yields immutable deterministic BatchTasks. `runner.worker` caches
prepared canonical problems and native adapters locally, samples once per physical
batch, decodes paired selected syndromes and returns rows with complete service
timing. `runner.pipeline` owns run setup, bounded spawn scheduling, serial execution,
parent-only writes and status propagation. `storage` defines versioned Arrow data,
validates pairing/semantics and commits two atomic shards. `provenance` preserves
source bytes/patches, build/environment identity and clock diagnostics. Saved-sample
replay reuses source artifacts and physical rows. No native object is pickled.

See pipeline.md and each module README for supported behavior and limits.

## Stage 6 analysis

The installed top-level analysis package separates io (verified manifest/paired
loading and selection), statistics (protected grouping, summed counts, Wilson,
quantiles/ECDF), plots (standalone PNG/PDF), report (shared export workflow), and
validation (exact saved-run comparisons). Importing analysis loads no decoder/provider
modules. The notebook calls these APIs and displays exported artifacts only.

A clean acceptance workspace clones pinned source bytes into independent Git checkouts
and creates a new search_decimation prefix. Build restoration includes ignored authored
C++ sources; current native objects are never copied to acceptance. Source ZIP captures
now include analysis/notebook code and explicitly audited ignored sources.
