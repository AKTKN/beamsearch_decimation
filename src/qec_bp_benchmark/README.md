# Active package reset

Active simulator config and decoder services expose `beam8`, configurable-order
`bposd`, and pinned upstream `relay_bp`. `af_bp_service.py` offers a separate
callable AF-BP-1.0 native service but is not registered with the simulator.
Decimation details below are historical
and their source is preserved in legacy paths or excluded from CMake.

---

# Benchmark package

config.load_config returns frozen validated settings and resolved grids;
identity functions separately hash scientific, decoder, sampling and run records.
Configuration imports no numerical/native libraries, allowing thread bootstrap.

circuits creates full physical Z-memory templates, validates provider bookkeeping,
applies common noise and selects Z detectors. dem converts undecomposed models
into canonical read-only CSC matrices and mechanism priors. artifacts prepares,
verifies and loads immutable content-addressed instances. bp.FloodingBP owns its
graph/prior copies and wraps a single native call to the audited ldpc fork. BPResult
contains explicit status, optional valid correction and owned diagnostic arrays.

_native is the project-owned compiled exhaustive search boundary.
See each subdirectory README, docs/architecture.md and docs/reference_bp.md.
Tests: tests/test_config.py, test_circuits.py, test_dem.py, test_bp.py and native/
plus actual pinned-dependency and pristine BP-OSD regression checks.

Stages 4–5: native/search.hpp implements the complete exhaustive screened decoder;
decoders.DecoderAdapter provides all three native services with independent parity
validation. runner owns deterministic paired tasks, spawn/serial execution, timing
and replay; storage owns strict Arrow schemas and parent-only paired commits;
provenance archives actual source/build/environment bytes and metadata.

The separately installed top-level analysis package validates saved runs, computes
count-based uncertainty and per-shot timing distributions, and exports reports.
It imports no circuit provider or decoder. Notebook consumers call that public API.
See docs/analysis.md, docs/schema.md and docs/acceptance_report.md for the full
interface, final clean-build evidence and finite-smoke limitations.


Hybrid migration Stage 1 adds `config.Hybrid` and its nested strict models, with
resolved per-cycle budgets and explicit warm/cold/search-only identities. `Bposd0`
uses actual upstream BP+CS0. Legacy configuration defaults are unchanged. The native hybrid is now callable;
run/replay remains guarded until Stage 4 implements v2 tables. See ../../docs/hybrid_migration.md for
native ownership, pending APIs, source hashes and subsequent storage/analysis work.

Stages 4–5 connect hybrid adapters to worker-owned event export, parent-only v2
storage and saved-data paired hypothesis analysis. See docs/hybrid_data.md for
state/timing boundaries, nullable labels, exact schemas and consumer APIs.

Stage 6 supplies source-only restoration/build verification and a repeatable bounded
E2E CLI at python_scripts/accept_hybrid.py. Final logs and limits are indexed in
STATUS.md and docs/hybrid_acceptance.md; required decoder/data/consumer paths are
complete. Production rates remain an explicit user choice.

`SearchBP` is the active persistent Q/G search plus hard-fixation BP-state beam.
Fixed columns are excluded from native message updates and fixed ones modify the
residual syndrome. Search, scheduling, state inheritance, ranking, solutions and
direct CS0 stay native; Python owns preparation, persistence and offline labels.

SEARCH-BP-2.0 Stage 3 exposes `_native.SearchBPStage3` for Steps 1–4 only, with
fork-owned BP and project-owned scores/local search. See docs/search_bp_stage3.md for the two local-variable policies.

Stage 4 additionally exposes `_native.SearchBP2Decoder` for full native recursive
decoding with a compact result. Stage 5 integrates it into the existing simulator with truth-free dispatch and
six-field results only. See docs/search_bp_stage5.md.

The separate `LPM-DP-BP-1.0` service is complete: native candidate generation,
hard-decimated warm BP, bounded retention and optional OSD are exposed through one
truth-free call and the five-field `lpm_dp_results/1` contract. See
docs/lpm_dp_final_report.md.
