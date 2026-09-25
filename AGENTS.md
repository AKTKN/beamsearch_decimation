# AF-BP benchmark workspace

The active branch is `af-bp-v1`, based on the latest `origin/search-bp-lpmdp-v1`.
This stage reset the active package around a future AF-BP comparison. AF-BP and
Relay-BP are not implemented or registered yet. Active decoder profiles are only
`beam8` and `bposd`; the latter accepts a nonnegative `osd_order` option. Never
label historical `bposd_ms30_cs0` or `bposd_ms30_cs10` results as new `bposd`.

Use the `search_decimation` conda environment. Physical production rates are
user-supplied; never launch a production sweep implicitly. The active smoke
configuration is `config/baselines.yaml.example`. The current result contract is
`docs/simulation_output.md`: one physical shot per row and fields `shot_id`,
`decoder_name`, `logical_error`, `latency_ns`, `total_iterations`. The iteration
count is the actual total across all BP calls; OSD adds zero. Beam8 has an
instrumentation-only upstream patch to count all masked paths. Preserve the
complete `DecoderAdapter.decode` wall-time boundary.

Do not change the simulator's circuit providers, noise, DEM, physical sampling,
syndrome/truth projection, paired shots, worker scheduling, logical comparison,
or BB144 construction without a separately authorized scientific change. No truth
enters a decoder. Preserve all 12 BB logical Z observables and DEM correlations.

Old screened decimation, Hybrid Search/BP, SEARCH-BP and LPM-DP are legacy. Their
configuration/service/storage snapshots and tests are under named `legacy/`
paths. Project-native source headers and fork reference/hybrid source remain in
place as historical source but are excluded from the active CMake build and
active decoder registry. Historical run evidence and scientific results are
immutable. See `docs/legacy/decimation/README.md` and the prior full AGENTS
instructions archived there for historical reproduction.

Stage 2 added opt-in `ldpc.af_bp` C++ parallel/serial/qDither BP engines without
changing upstream BP-OSD. Stage 3 added the standalone C++ graph factorization
core under `src/af_bp_core/`. Neither component is registered with the active
simulator, and the complete AF-BP decoder loop does not exist yet. Preserve
the TeX-defined sparse support, exact graph equivalence, local net-cycle score,
and strict rediscovery after every accepted transform. Keep typed public APIs,
deterministic ordering, checked native boundaries and no fast-math.

Active checks:

```bash
conda activate search_decimation
scripts/build_dependencies.sh --check
python python_scripts/validate_config.py config/baselines.yaml.example
python -m pytest -q
scripts/run_benchmark.sh config/baselines.yaml.example
```

New runs use fresh output directories; no in-place resume. Do not rewrite old
Parquet data or archived source bytes. Update active docs and STATUS.md with
actual evidence and limits.
