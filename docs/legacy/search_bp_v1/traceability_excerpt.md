SEARCH-BP-1.0 traces from `docs/specifications/search_bp_specification.md` and the
adjacent JSON data contract to native `search_bp*.hpp` and
`hard_fixed_min_sum.hpp`, `storage/search_bp*.py`, the three
`tests/test_search_bp_*.py` modules and `tests/native/test_search_bp.cpp`.

| SEARCH-BP-1.0 requirement | Implementation | Behavioral evidence |
|---|---|---|
| Scalar per-cycle expansions; no global expansion or generated-node cap | `SearchBPSearch`, `SearchSession::advance` | removed-option rejection and native 96-child/one-expansion test |
| Beam width replaces admissions and limits retained states | `search_bp.hpp` proposal/reconcile | `test_search_bp_decoder.py` beam/admission checks |
| Fixed per-visit `max_iteration`; no total cap | `search_bp.hpp` visit loop | fixed quota and multi-cycle continuation tests |
| Structural 0/1 fixation and residual syndrome | `hard_fixed_min_sum.hpp` | native fixed-edge/residual assertions |
| Original-H validation and physical scoring | `search_bp.hpp::submit`, `Model::cost` | Python parity/repeatability and native tests |
| Strict new identity and removed options | `config.SearchBP` | rejection matrix in `test_search_bp_config.py` |
| Decoder-opaque simulation timing decomposition | `benchmarking/simulation.py`, runner/worker/storage opt-in scopes | `test_simulation_benchmark.py`; bounded JSON report |
| Bounded search_bp shot streaming and grouped Parquet writes | native column export, bounded parent queue, `ShotChunkBuffer`, `ResultStore` column input | native row/column equality, full/final group unit test, serial and two-worker row-group tests |
