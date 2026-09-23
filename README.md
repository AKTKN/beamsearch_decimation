# Circuit-level BP benchmark

The current simulation runner uses a minimal result layout: a local-time
`YYYY_MM_DD_HH_MM_<config-hash-8>` directory containing only `data/` and
`config_resolved.json`. Data filenames begin with code, distance, rounds, physical
rate and basis, for example `bb72_d6_r6_p003_Z_results.parquet`. See
[minimal simulation output](docs/simulation_output.md).

All seven historical implementation stages are complete: physical Z-memory circuits, canonical
DEM artifacts, native screened-decimation search using the forked ldpc flooding
kernel, unchanged BP-OSD and published beam baselines, paired serial/spawn simulation,
exact replay, verified analysis, figures and executable notebooks. A fresh pinned-source
build passed the full acceptance suite. See [acceptance report](docs/acceptance_report.md)
and [status](STATUS.md) for actual evidence and limits.


The separate hybrid migration has completed Stages 1-6: strict configuration,
audited stateful min-sum and OSD-only fork interfaces, and native bounded search
with warm/cold/search-only profiles and CPU/wall telemetry. The hybrid is callable
through `DecoderAdapter` and paired run/replay with v2 storage and reports. See
[the native API](docs/hybrid_native.md) and [current status](STATUS.md).
The upstream `bposd_ms30_cs0` baseline remains runnable through the existing runner.

The public `search_bp` identity denotes **SEARCH-BP-2.1**. The
[active implementation and final audit](docs/search_bp_implementation.md) maps all
seven TeX steps to code and documents exact defaults, memory and validation limits.
Stage 4 completes the
native decoder as `_native.SearchBP2Decoder`: global candidate admission,
inherited BP, reliability-based retention, fresh recursive searches and OSD-0.
[The API, conventions and work bounds](docs/search_bp_stage4.md) describe its small
result and deterministic policies. **Stage 5 integrates the simulator** through the truth-free adapter and saves
only six-field `<condition>_results.parquet` files plus resolved config. See
[configuration, schema and smoke evidence](docs/search_bp_stage5.md).
[Root refined.tex](refined.tex) is normative; [the design map](docs/search_bp_v2_design.md)
records its equations and stage decisions. The fork owns the
[stateful decimated BP kernel](docs/decimated_bp.md); the project owns all search
and orchestration. No production simulations were run for this stage.
SEARCH-BP-1.0 sources, bindings, contracts and tests are
preserved under `legacy/search_bp_v1` areas and excluded from the active build.

The separate LPM-DP work is complete through native Stage 3. Its distinct
`LPM-DP-BP-1.0` state machine uses per-parent local-parity candidates, warm-started
hard-decimated BP and bounded post-BP retention; it does not use SEARCH-BP search
scores or global admission. It has no Python/simulator registration yet. See
[the native Stage-3 report](docs/lpm_dp_stage3.md).

New simulations save one six-column result file per condition: shot identity,
decoder name, logical error, full service wall latency, and OSD-called flag.
Baseline decoder kernels and simulation physics are unchanged.

```bash
# Create once; use the existing environment if already installed.
conda create -n search_decimation --file environment.conda.lock.txt
conda activate search_decimation
scripts/setup_local_files.sh
scripts/build_dependencies.sh
python python_scripts/audit_dependencies.py
scripts/build_dependencies.sh --check
python -m pytest -q

python python_scripts/validate_config.py config/search_bp.yaml.example
# For a runnable baseline check: scripts/run_benchmark.sh config/bposd_cs0_smoke.yaml.example
python -c "from analysis.simple_search_bp import summarize_run; print(summarize_run('/path/to/run'))"
```

Add `-v` or `--verbose` to simulation commands for preparation and saved-batch
progress on stderr, for example `scripts/run_benchmark.sh config/hybrid_smoke.yaml.example --verbose`.
stdout remains the completed run directory. Progress updates once per saved batch.

The search_bp template is a runnable bounded smoke configuration. Its physical grid
is not production guidance. Baseline-only configurations remain runnable. BB
retains all twelve logical Z observables. Historical soft-hint and HSBP-FB
configurations are under `config/legacy/hybrid/`.

Historical screened-reference/CS10 configs and existing local main.yaml are in
`config/legacy/`. Their scientific settings and resolved data/output paths are
preserved. Replay remains legacy-only. Current analysis uses an independent
`config/analysis.yaml.example`; the preserved consumer implementation is available
as `analysis.legacy` and through `scripts/legacy/`. See [analysis migration](docs/analysis_migration.md).

Edit `noise.rates` or `noise.sweep` (exactly one), `decoders` entries, sampling counts
and execution workers for the requested experiment. The production template rejects
its empty physical grid until edited. The example p=0.001 is for implementation
validation only; these smoke data establish no decoder advantage or tail precision.

Immutable circuits/DEMs/matrices/maps remain execution inputs in `simulation_data/`
and are never copied into a result. Runs write the minimal layout under output.root
(default `assets/runs/`). Interrupted runs may contain readable partial Parquet
data; in-place resume and manifest-based replay are not part of the current runner.

[Build](docs/build.md), [fork maintenance](docs/fork_maintenance.md),
[pipeline/replay/timing](docs/pipeline.md), [scientific contract](docs/benchmark_contract.md),
[YAML](docs/configuration.md), [schema](docs/schema.md), [analysis](docs/analysis.md),
[extension points](docs/extensions.md), [traceability](docs/traceability.md),
[source locks](external_lib/manifest.lock.json).
The algorithm specification and all six supplied reference modules are preserved.

## Git distribution

See [repository setup](docs/distribution.md). Editable `config/*.yaml` files,
analysis notebooks, scientific artifacts, reports, caches and dependency checkouts
are local and ignored. Versioned `.example` templates initialize a new checkout
without replacing local work. Dependency commits and fork patches remain versioned.

Historical Hybrid Stages 4–5 evidence and limitations remain documented in
[hybrid acceptance](docs/hybrid_acceptance.md). Those manifest/replay acceptance
commands are legacy evidence, not the current minimal-output workflow.
