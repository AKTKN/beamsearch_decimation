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
