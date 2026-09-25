# Historical decimation families

Stage 1 removed screened decimation, Hybrid Search/BP, SEARCH-BP and LPM-DP
from the active configuration registry, decoder adapter and CMake build.
Their former config and decoder-service definitions are copied into
`src/qec_bp_benchmark/legacy/decimation/`. Historical top-level templates
are under `config/legacy/decimation/`; older templates remain in the existing
`config/legacy/` tree. The current six-field SEARCH-BP and five-field LPM-DP
storage contract is archived under
`src/qec_bp_benchmark/storage/legacy/decimation/minimal.py`, and its direct
saved-data reader under `analysis/legacy/decimation/`. Default pytest excludes
`tests/legacy/`; the moved focused Python tests are in
`tests/legacy/decimation/`.

Project-native source headers remain under `src/qec_bp_benchmark/native/` to
avoid disruptive moves and to retain source history. They are excluded from
the active CMake build and have no active decoder registration. The fork's
reference/hybrid source and bindings remain in `external_lib/ldpc` for
historical restoration but the active dependency build does not compile them.
The old native-build script is `python_scripts/legacy/build_dependencies_decimation.py`.

The historical suite targets the pre-migration package/config/build and is
runnable from a clean worktree at commit `7e16a1b7ce22076f1ce005675559b76ee046009b`
with `conda run -n search_decimation python -m pytest -q`; it is not an active
suite against the new registry. Previously saved runs and evidence must retain
their exact identities and schemas. Historical implementation documents remain
in `docs/` and `docs/legacy/`; earlier root instructions and README are copied
here for context. Those documents describe historical behavior.
