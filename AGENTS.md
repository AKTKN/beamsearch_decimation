# AF-BP benchmark workspace

The active branch is `af-bp-v1`, based on the latest `origin/search-bp-lpmdp-v1`.
The active package benchmarks AF-BP on paired physical samples. Active decoder
profiles are `af_bp`, `beam8`, `bposd`, and pinned `relay_bp`; the latter uses
upstream Rust `RelayDecoderF64.decode_detailed` and exact total iterations.
`bposd` accepts a nonnegative `osd_order` option. Never label historical
`bposd_ms30_cs0` or `bposd_ms30_cs10` results as new `bposd`.

Use the `search_decimation` conda environment. Physical production rates are
user-supplied; never launch a production sweep implicitly. The active smoke
configuration is `config/baselines.yaml.example`. The current result contract is
`docs/simulation_output.md`: one physical shot per row and fields `shot_id`,
`decoder_name`, `logical_error`, `latency_ns`, `total_iterations`, `converged`,
`initial_bp_converged`, and `first_transform_converged`. New schema metadata
is `benchmark_results/3`; old `/2` runs are read-only and convergence is not
inferred from their logical-error field. BP-OSD convergence is its BP-stage
result before OSD. The iteration count is the actual total
across all BP calls; OSD adds zero. Beam8 has an
instrumentation-only upstream patch to count all masked paths. Preserve the
complete `DecoderAdapter.decode` wall-time boundary.
Relay source is pinned at `d185194ba0cb4101ced4340d82b2ee6d42f225f0`
under `external_lib/relay`, built with locked maturin. Preserve upstream
Apache-2.0 and IBM attribution; do not modify its scientific implementation.
Use single-shot `decode_detailed`, not Relay's parallel batch API. Explicit
gamma arrays are rejected until a reproducible source contract exists.

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
core under `src/af_bp_core/`. Stage 4 added the native AF-BP-1.0 decoder state
machine, one-call truth-free Python boundary and a separate CMake extension.
Stage 6 registers that service and keeps all physical sampling and worker
logic intact. Preserve the TeX-defined sparse
support, exact graph equivalence, local net-cycle score, strict rediscovery,
exact BP iteration counts, immutable physical priors and original-H validation.
Keep typed public APIs, deterministic ordering, checked native boundaries and
no fast-math.

Active checks:

```bash
conda activate search_decimation
scripts/build_dependencies.sh --check
python python_scripts/validate_config.py config/baselines.yaml.example
python python_scripts/validate_config.py config/af_bp_smoke.yaml.example
python -m pytest -q
scripts/run_benchmark.sh config/baselines.yaml.example
```

New runs use fresh output directories; no in-place resume. Do not rewrite old
Parquet data or archived source bytes. Update active docs and STATUS.md with
actual evidence and limits.
Stage 6 integration and bounded BB144 evidence are in `docs/af_bp_stage6.md`.
Stage 7 clean restoration, mathematical checks, sanitizer results, memory audit
and extraction boundaries are in `docs/af_bp_final_report.md`. Run
`bash scripts/check_af_bp_native.sh debug`, `asan` and `ubsan` for the two
active native tests. The weighted net-cycle reduction is nonnegative for a
valid biclique and nonnegative weights; the final report gives the proof.
